#!/usr/bin/env python3
"""Fix only independently evidenced wheel diffuse R/B swaps.

Usage: fix_characar_wheels.py GAME_DATA WPK_DIRECTORY NEW_DIRECTORY
GAME_DATA contains characar and changewheel. Never overwrites inputs. JSON
report on stdout. Default uses conservative TGA reference evidence. Optional
--source-engine-order uses exact source re-encoding and static driver-order
inference; it has not been verified on a running device.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent / "stage"))
import scene
import lualite
import pack

WHEELS = {0x100, 0x101, 0x102, 0x103}
MAX_PIXELS = 4096 * 4096


def span(data, off, size):
    if off < 0 or size < 0 or off > len(data) or size > len(data) - off:
        raise ValueError("out-of-bounds file range")


def parse_wpk(data):
    span(data, 0, 32)
    magic, nt, nc, nb, _, to, co, bo = struct.unpack_from("<4sIIIfIII", data)
    if magic not in (b"WPK2", b"WPK3") or nt > 65535 or nc > 100000 or nb > 1000000:
        raise ValueError("invalid WPK header")
    bs = 28 if magic == b"WPK3" else 20
    if (to, co, bo) != (32, 32 + nt * 64, 32 + nt * 64 + nc * 36):
        raise ValueError("invalid table layout")
    start = bo + nb * bs
    span(data, 0, start)
    textures, ranges = [], []
    for i in range(nt):
        name, w, h, fmt, off, size = struct.unpack_from("<48sHHIII", data, to + i * 64)
        if b"\0" not in name or not w or not h or w*h > MAX_PIXELS or off < start:
            raise ValueError("invalid texture")
        name = name.split(b"\0", 1)[0].decode("latin1")
        if not name or (fmt in (0, 1, 2) and size != w*h*2):
            raise ValueError("invalid texture size or name")
        span(data, off, size)
        textures.append(dict(name=name, w=w, h=h, fmt=fmt, off=off, size=size))
        ranges.append((off, off + size))
    sr = sorted(ranges)
    if any(a[1] > b[0] for a, b in zip(sr, sr[1:])):
        raise ValueError("overlapping texture data")
    groups = [set() for _ in range(nb)]
    for i in range(nc):
        *_, first, count, group = struct.unpack_from("<6fIII", data, co + i*36)
        if first > nb or count > nb-first:
            raise ValueError("invalid batch interval")
        for j in range(first, first+count):
            groups[j].add(group)
    usage = [set() for _ in range(nt)]
    for i in range(nb):
        t, _, vo, nv, io, ni = struct.unpack_from("<HHIIII", data, bo+i*bs)
        if not groups[i] or vo < start or io < start:
            raise ValueError("orphan batch or invalid data")
        for off, size in ((vo, nv * (32 if bs == 28 else 24)), (io, ni*2)):
            span(data, off, size)
            if size and any(off < b and off+size > a for a,b in ranges):
                raise ValueError("geometry overlaps texture")
        if t != 65535:
            if t >= nt:
                raise ValueError("invalid diffuse index")
            usage[t].update("wheel" if g in WHEELS else "other" for g in groups[i])
        if bs == 28:
            _, _, env, spec, _ = struct.unpack_from("<BBHHH", data, bo+i*bs+20)
            for j in (env, spec):
                if j != 65535:
                    if j >= nt:
                        raise ValueError("invalid material index")
                    usage[j].add("material")
    return textures, usage


def basename(name):
    return Path(name.replace("\\", "/").split("/")[-1]).stem.casefold()


def image_name(f, image):
    return image if isinstance(image, str) else f.string(image[22]) if image is not None else None


def source_wheels(path):
    f, meshes = scene.meshes(str(path))
    wheel, other, material = {}, set(), set()
    for m in meshes:
        name = image_name(f, m["image"])
        if name:
            name = name.casefold()
            if any(x in ("WHEEL_L", "WHEEL_R") for x in m["path"]):
                wheel.setdefault(name, []).append(m)
            else:
                other.add(name)
        for key in ("env_image", "spec_image"):
            name = image_name(f, m["state"].get(key))
            if name:
                material.add(name.casefold())
    return wheel, other, material


def uv_mask(meshes, w, h):
    mask = Image.new("1", (w, h))
    draw = ImageDraw.Draw(mask)
    for m in meshes:
        uv = m["verts"].get("uv")
        tri = np.asarray(m["tris"])
        if uv is None or tri.ndim != 2 or tri.shape[1] != 3 or not len(tri):
            raise ValueError("missing UV triangles")
        if not np.isfinite(uv).all() or np.min(uv) < -0.0001 or np.max(uv) > 1.0001 or np.min(tri) < 0 or np.max(tri) >= len(uv):
            raise ValueError("unsupported UV coordinates")
        for t in tri:
            draw.polygon([(float(uv[j][0])*(w-1), float(uv[j][1])*(h-1)) for j in t], fill=1)
    a = np.asarray(mask, dtype=bool)
    if a.sum() < 32:
        raise ValueError("insufficient UV coverage")
    return a


def decode16(data, t):
    p = np.frombuffer(data, dtype="<u2", count=t["w"]*t["h"], offset=t["off"]).reshape(t["h"], t["w"]).astype(np.uint32)
    fmt = t["fmt"]
    if fmt == 0:
        rgb = np.stack((((p>>11)&31)*255//31, ((p>>5)&63)*255//63, (p&31)*255//31), axis=-1)
        a = np.full(p.shape, 255)
    elif fmt == 1:
        rgb = np.stack(((p>>12)&15, (p>>8)&15, (p>>4)&15), axis=-1)*17
        a = (p&15)*17
    elif fmt == 2:
        rgb = np.stack(((p>>11)&31, (p>>6)&31, (p>>1)&31), axis=-1)*255//31
        a = (p&1)*255
    else:
        raise ValueError("unsupported texture format")
    return rgb.astype(np.int16), a


def swap16(raw, fmt):
    p = np.frombuffer(raw, dtype="<u2").copy()
    if fmt == 0:
        p = (p&0x07e0) | ((p&0xf800)>>11) | ((p&0x001f)<<11)
    elif fmt == 1:
        p = (p&0x0f0f) | ((p&0xf000)>>8) | ((p&0x00f0)<<8)
    elif fmt == 2:
        p = (p&0x07c1) | ((p&0xf800)>>10) | ((p&0x003e)<<10)
    else:
        raise ValueError("unsupported texture format")
    return p.astype("<u2").tobytes()


def classify(rgb, alpha, tga, mask):
    if tga.shape != (*alpha.shape, 4):
        return {"status":"unknown", "reason":"reference size differs"}
    ref = tga[::-1].astype(np.int16)
    valid = mask & (alpha >= 128) & (ref[:,:,3] >= 128)
    n = int(valid.sum())
    if n < 32:
        return {"status":"unknown", "reason":"insufficient visible pixels", "pixels":n}
    p, q = rgb[valid], ref[:,:,:3][valid]
    before = float(np.abs(p-q).mean()); after = float(np.abs(p[:,[2,1,0]]-q).mean())
    chroma = float(np.abs(q[:,0]-q[:,2]).mean())
    result = dict(status="unknown", reason="ambiguous or mismatched reference", pixels=n, mae_before=before, mae_after=after, reference_rb_difference=chroma)
    if chroma < 12:
        result["reason"] = "near-grey reference"
    elif after <= 10 and before >= 15 and before-after >= 12 and before >= 2.5*max(after, .01):
        result.update(status="swap", reason="strong vertically flipped reference match")
    elif before <= 10 and after-before >= 12 and after >= 2.5*max(before, .01):
        result.update(status="unchanged", reason="already matches reference")
    return result


def process(data, source, refs):
    textures, usage = parse_wpk(data)
    wheels, other, material = source_wheels(source)
    out, report = bytearray(data), []
    for name, meshes in wheels.items():
        row = {"source_texture":name}; report.append(row)
        matches = [i for i,t in enumerate(textures) if t["name"].casefold() == name]
        if len(matches) != 1 or name in other or name in material:
            row.update(status="unknown", reason="ambiguous or reused source texture"); continue
        i = matches[0]; t = textures[i]; row["wpk_texture"] = t["name"]
        if usage[i] != {"wheel"}:
            row.update(status="unknown", reason="texture referenced outside wheel diffuse"); continue
        candidates = refs.get((basename(name), t["w"], t["h"]), [])
        if len(candidates) != 1:
            row.update(status="unknown", reason="missing or ambiguous exact basename and size references", references=len(candidates)); continue
        try:
            rgb, alpha = decode16(data, t); mask = uv_mask(meshes, t["w"], t["h"])
            with Image.open(candidates[0]) as im:
                im.load(); ref = np.asarray(im.convert("RGBA"))
            row.update(classify(rgb, alpha, ref, mask)); row["reference"] = str(candidates[0])
            if row["status"] == "swap":
                off, n = t["off"], t["size"]
                out[off:off+n] = swap16(data[off:off+n], t["fmt"])
        except (OSError, ValueError, IndexError) as e:
            row.update(status="unknown", reason=str(e))
    return bytes(out), report or [{"status":"unknown", "reason":"no wheel diffuse meshes"}]


def source_from_lua(data, model):
    """Resolve only the real car.lua TireStatus.file[0], confined to data."""
    folder = data / "characar" / model
    lua = folder / "car.lua"
    for p in (data / "characar", folder, lua):
        if p.is_symlink():
            raise ValueError("symlink in car.lua path")
    values = lualite.Parser(lua.read_text(encoding="utf8"), {}).chunk()
    files = values["TireStatus"]["file"]
    if not isinstance(files, list) or not files or not isinstance(files[0], str):
        raise ValueError("missing TireStatus.file[0]")
    rel = Path(files[0].replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or rel.parts[0] != "data" or any(x in (".", "..") for x in rel.parts):
        raise ValueError("unsafe TireStatus.file[0]")
    path = data.joinpath(*rel.parts[1:])
    current = data
    for part in rel.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink in TireStatus.file[0]")
    if not path.is_file():
        raise ValueError("missing TireStatus.file[0] model")
    return path


def process_engine_order(data, source):
    """Statically inferred driver conversion, not verified on a running device."""
    textures, usage = parse_wpk(data)
    f, meshes = scene.meshes(str(source))
    wheels, other, material = {}, set(), set()
    for m in meshes:
        img = m.get("image")
        name = image_name(f, img)
        iswheel = any(x.startswith("WHEEL_") for x in m["path"])
        if iswheel and not name:
            raise ValueError("wheel mesh has no diffuse image")
        if name:
            key = name.casefold()
            if iswheel:
                wheels.setdefault(key, []).append(img)
            else:
                other.add(key)
        for attr in ("env_image", "spec_image"):
            name = image_name(f, m["state"].get(attr))
            if name:
                material.add(name.casefold())
    out, report = bytearray(data), []
    for name, images in wheels.items():
        row = {"source_texture": name, "method": "source-engine-order", "status": "unknown"}
        report.append(row)
        try:
            matches = [t for t in textures if t["name"].casefold() == name]
            named = [x for x in f.of_type("igImage") if x[22] is not None and image_name(f, x).casefold() == name]
            if len(matches) != 1 or len(named) != 1 or any(x is not named[0] for x in images) or name in other or name in material:
                raise ValueError("ambiguous or reused source texture")
            img = named[0]
            if img[6] is None or img[11] is None or img[6].i32 != 100 or img[11].i32 != 15:
                raise ValueError("source image is not order 100 format 15")
            t = matches[0]; row["wpk_texture"] = t["name"]
            index = textures.index(t)
            if usage[index] != {"wheel"}:
                raise ValueError("texture referenced outside wheel diffuse")
            with contextlib.redirect_stdout(sys.stderr):
                im = pack.decode_image(f, img)
            if im is None:
                raise ValueError("source image cannot be decoded")
            w, h, fmt, encoded = pack.encode16(im, max(t["w"], t["h"]))
            raw = data[t["off"]:t["off"] + t["size"]]
            if (w, h, fmt, encoded) != (t["w"], t["h"], t["fmt"], raw):
                raise ValueError("source encoding does not exactly match WPK texture")
            swapped = swap16(raw, fmt)
            if swapped == raw:
                row.update(status="unchanged", reason="R/B invariant")
            else:
                out[t["off"]:t["off"] + t["size"]] = swapped
                row.update(status="swap", reason="exact source bytes; inferred driver order conversion")
        except (OSError, ValueError, TypeError, AttributeError, IndexError, KeyError, struct.error) as e:
            row["reason"] = str(e)
    return bytes(out), report or [{"status": "unknown", "method": "source-engine-order", "reason": "no wheel diffuse meshes"}]


def collect_references(root):
    if not root.is_dir():
        raise ValueError("missing changewheel directory")
    result = {}
    for p in root.rglob("*"):
        if not p.is_file() or p.is_symlink() or p.suffix.casefold() != ".tga":
            continue
        try:
            with Image.open(p) as im:
                w,h = im.size
                if w*h > MAX_PIXELS: continue
                im.verify()
            result.setdefault((basename(p.name),w,h), []).append(p)
        except (OSError, ValueError):
            continue
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_dir", type=Path); ap.add_argument("wpk_dir", type=Path); ap.add_argument("output_dir", type=Path)
    ap.add_argument("--source-engine-order", action="store_true", help="opt in to static original-driver order inference; not verified on device")
    args = ap.parse_args(argv)
    data = args.data_dir.resolve(strict=True); src = args.wpk_dir.resolve(strict=True)
    output = args.output_dir.absolute(); output = output.parent.resolve(strict=True) / output.name
    if output.exists() or output.is_symlink() or output == src or src in output.parents or output == data or data in output.parents:
        ap.error("output must not exist and must be outside inputs")
    if not src.is_dir() or not (data/"characar").is_dir():
        ap.error("invalid input directories")
    refs = {} if args.source_engine_order else collect_references(data/"changewheel")
    os.mkdir(output); report = []; failed = False
    for p in sorted(src.glob("*.wpk")):
        if p.name.startswith("._"):
            continue  # AppleDouble metadata, not a WPK
        row = {"model":p.stem}; report.append(row)
        try:
            if p.is_symlink(): raise ValueError("symlinked WPK")
            original = p.read_bytes()
            if args.source_engine_order:
                igb = source_from_lua(data, p.stem)
                result, row["textures"] = process_engine_order(original, igb)
            else:
                igb = data/"characar"/p.stem/"tire2.igb"
                if not igb.is_file() or igb.is_symlink():
                    result = original; row["textures"] = [{"status":"unknown", "reason":"missing original tire2.igb"}]
                else:
                    result, row["textures"] = process(original, igb, refs)
                for item in row["textures"]: item["method"] = "tga-reference"
            with (output/p.name).open("xb") as f: f.write(result)
        except (OSError, ValueError, TypeError, IndexError, KeyError, struct.error) as e:
            failed = True
            row["error"] = str(e); row["textures"] = [{"status":"unknown", "reason":"malformed or unreadable input"}]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
