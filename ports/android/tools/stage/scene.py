"""Walk an IGB scene graph and pull out drawable meshes.

Node layout seen in WMMT3DX+ files (v8):
  igNode subclasses: s2 name, s3 bound, s5 flags, s7 child igNodeList
  igTransform:       s8 Matrix44f (row-major, translation in the last row)
  igAttrSet/igGeometry: s8 igAttrList
  igSceneInfo:       s5 root node
  igGeometryAttr2:   s4 igVertexArray2, s5 igIndexArray, s6 igPrimLengthArray,
                     s7 prim type (3 = triangle list, 4 = triangle strip), s8 prim count
  igVertexArray2:    s3 igObjectList of igVertexData
  igVertexData:      s3 igUnsignedCharList (s4 -> memory); s6 stride.
                     Memory starts with a declaration: one stream byte, then
                     (usage, format) byte pairs, then a 0xff terminator.
                     format high nibble = byte size. usage 1 pos, 2 color, 3 normal, 4 uv0.
  Older files (stage_common/gurdrail_*.igb) use igGeometryAttr1_5 instead:
                     s4 igVertexArray1_1, s5 igIndexArray, s6 prim type, s7 prim count,
                     s13 igPrimLengthArray1_1 (s2 memory of u32 lengths)
  igVertexArray1_1:  s2 memory of 20 block refs (0 pos f32x3, 2 color RGBA u8x4,
                     11 uv0 f32x2), s3 vertex count
  igSimpleShader:    a node whose attrs sit in s11 igShaderData (s2 igAttrListList);
                     s12 igTextureTransformMovieProcessor animates the texture matrix:
                     s2 f32 frames per second, s3 columns, s4 rows, s5 frames
"""
import struct

import numpy as np

from igb import IGB

USAGE = {1: "pos", 2: "color", 3: "normal", 4: "uv"}


def obj_list(f, lst):
    if lst is None:
        return []
    n = lst[2].i32
    data = f.ref(lst[4])
    if data is None or data.mem is None or n <= 0:
        return []
    return [f.objects[i] for i in struct.unpack_from("<%di" % n, data.mem)]


def mem_of(f, field):
    o = f.ref(field)
    return o.mem if o is not None else None


def parse_decl(mem):
    """Return (elements, header_len); elements = [(usage, offset, size)]."""
    p = 1
    off = 0
    elems = []
    while p + 1 < len(mem):
        usage, fmt = mem[p], mem[p + 1]
        if usage == 0xFF:
            break
        if usage not in USAGE:
            raise ValueError("unknown vertex usage 0x%02x" % usage)
        size = fmt >> 4
        elems.append((USAGE[usage], off, size))
        off += size
        p += 2
    return elems, p + 1


def decode_vertices(f, va):
    vds = obj_list(f, f.ref(va[3]))
    if not vds:
        return None
    vd = vds[0]
    stride = vd[6].i32
    mem = mem_of(f, f.ref(vd[3])[4])
    elems, hdr = parse_decl(mem)
    if sum(e[2] for e in elems) != stride or (len(mem) - hdr) % stride:
        raise ValueError("decl %s does not match stride %d" % (elems, stride))
    n = (len(mem) - hdr) // stride
    raw = np.frombuffer(mem, dtype=np.uint8, count=n * stride, offset=hdr).reshape(n, stride)
    out = {}
    for name, off, size in elems:
        chunk = np.ascontiguousarray(raw[:, off:off + size])
        if name == "pos":
            # (half floats in a few: the driving school Atenza's tyres and plate)
            out[name] = (chunk.view("<f4") if size == 12 else chunk.view("<f2").astype(np.float32)).reshape(n, 3)
        elif name in ("normal", "uv"):
            out[name] = chunk.view("<f2").astype(np.float32).reshape(n, size // 2)
        elif name == "color":
            out[name] = chunk[:, [2, 1, 0, 3]]  # stored RGBA; callers expect BGRA
    return out


# the old format's normals (block 1): read only when asked (pack_cars.py's GET screen wheels),
# so the packs made before them stay as they were
NORMALS_1_1 = False


def decode_vertices_1_1(f, va):
    n = va[3].i32
    refs = struct.unpack_from("<20i", f.ref(va[2]).mem)

    def block(i, dtype, width):
        if refs[i] < 0:
            return None
        return np.frombuffer(f.objects[refs[i]].mem, dtype=dtype, count=n * width).reshape(n, width)

    out = {"pos": block(0, "<f4", 3).astype(np.float32)}
    nrm = block(1, "<f4", 3) if NORMALS_1_1 else None
    if nrm is not None:
        out["normal"] = nrm.astype(np.float32)
    col = block(2, "u1", 4)
    if col is not None:
        out["color"] = col[:, [2, 1, 0, 3]]  # stored RGBA; callers expect BGRA
    uv = block(11, "<f4", 2)
    if uv is not None:
        out["uv"] = uv.astype(np.float32)
    return out


def decode_indices(f, g, nverts):
    old = g.type == "igGeometryAttr1_5"
    prim = g[6].i32 if old else g[7].i32
    ia = f.ref(g[5])
    if ia is not None:
        cnt = ia[3].i32
        idx = np.frombuffer(mem_of(f, ia[2]), dtype="<u2", count=cnt).astype(np.int32)
    else:
        idx = np.arange(nverts, dtype=np.int32)
    if prim == 3:
        return idx.reshape(-1, 3)
    if prim == 4:
        pla = f.ref(g[13] if old else g[6])
        lengths = [nverts]
        if pla is not None:
            n = pla[3].i32
            mem = f.ref(pla[2]).mem if old else mem_of(f, pla[2])
            lengths = list(struct.unpack_from("<%dI" % n, mem))
        tris = []
        start = 0
        for ln in lengths:
            s = idx[start:start + ln]
            for i in range(ln - 2):
                a, b, c = s[i], s[i + 1], s[i + 2]
                if a == b or b == c or a == c:
                    continue
                tris.append((a, b, c) if i % 2 == 0 else (b, a, c))
            start += ln
        return np.array(tris, dtype=np.int32).reshape(-1, 3)
    raise ValueError("unsupported primitive type %d" % prim)


def texture_image(f, attrs):
    """Diffuse (unit 0) texture: an igImage object, or the image name of an
    external texture (igExternalInfoEntry: s7 "<name> <params>", s9 file)."""
    for a in attrs:
        if a.type == "igTextureBindAttr" and a[2].i32 == 0:
            ref = a[4].i32
            if ref in f.externals:
                return f.string(f.externals[ref][1][7]).split(" ")[0]
            tex = f.ref(a[4])
            if tex is not None and tex.type == "igTextureAttr":
                return f.ref(tex[12])
    return None


def bound_image(f, attrs, unit):
    """The igImage an igTextureBindAttr binds to texture unit `unit`, or None."""
    for a in attrs:
        if a.type == "igTextureBindAttr" and a[5] is not None and a[5].i32 == unit:
            tex = f.ref(a[4])
            if tex is not None and tex.type == "igTextureAttr":
                return f.ref(tex[12])
    return None


def bound_external(f, attrs, unit):
    """The library name (textures.igb) an igTextureBindAttr binds to texture unit `unit`
    through an igExternalInfoEntry, or None."""
    for a in attrs:
        if a.type == "igTextureBindAttr" and a[5] is not None and a[5].i32 == unit and a[4].i32 in f.externals:
            return f.string(f.externals[a[4].i32][1][7]).split(" ")[0]
    return None


def car_shader(f, attrs):
    """The arcade's car programs (Cg compiled to ARB, kept in the car IGBs): 1 for car.cg
    (body paint: sphere-mapped EnvMapTexture on unit 1, uniformEnvMapPower, specular),
    2 for car_blend.cg (glass, lamps, emblems: SpecularMapTexture on unit 2 mixes the
    environment in); None when the attrs bind no vertex program."""
    for a in attrs:
        if a.type == "igVertexShaderBindAttr":
            prog = f.ref(a[4])
            src = f.string(prog[5]) if prog is not None and prog[5] is not None else ""
            return 2 if "car_blend.cg" in src else 1 if "car.cg" in src else None
    return None


def shader_attrs(f, node):
    data = f.ref(node[11])
    if data is None:
        return []
    return [a for lst in obj_list(f, f.ref(data[2])) for a in obj_list(f, lst)]


def movie(f, node, attrs):
    """Texture flipbook of an igSimpleShader: (fps, cols, rows, frames, uv scale) or None"""
    proc = f.ref(node[12])
    if proc is None or proc.type != "igTextureTransformMovieProcessor":
        return None
    scale = (1.0, 1.0)
    for a in attrs:
        if a.type == "igTextureMatrixAttr":
            m = struct.unpack("<16f", a[4].raw)
            scale = (m[0], m[5])
    return (proc[2].f32, proc[3].i32, proc[4].i32, proc[5].i32, scale)


def meshes(path):
    """Yield dicts: name, matrix (4x4), image (igImage obj or None), verts, tris, state,
    path (names of the igGroups above)."""
    f = IGB(path)
    info = f.of_type("igSceneInfo")
    roots = [f.ref(info[0][5])] if info else []
    out = []

    def walk(node, mat, image, state, path=()):
        if node is None or node.mem is not None:
            return
        if node.type == "igGroup" and node[2] is not None:
            path = path + (f.string(node[2]),)
        if node.type == "igTransform" and node[8] is not None:
            m = np.frombuffer(node[8].raw, dtype="<f4").reshape(4, 4)
            mat = m @ mat
        attrs = obj_list(f, f.ref(node[8])) if node.type in ("igAttrSet", "igGeometry") else []
        state = dict(state)
        if node.type == "igSimpleShader":
            attrs = shader_attrs(f, node)
            state["movie"] = movie(f, node, attrs)
        img = texture_image(f, attrs)
        if img is not None:
            image = img
        for a in attrs:
            if a.type == "igBlendStateAttr":
                state["blend"] = bool(a[4].i32)
            elif a.type == "igBlendFunctionAttr":
                state["blend_func"] = (a[4].i32, a[5].i32)
            elif a.type == "igFloatConstantAttr":  # car.cg's uniformEnvMapPower
                state["env_power"] = a[4].f32
        if any(a.type == "igVertexShaderBindAttr" for a in attrs):
            state["car_shader"] = car_shader(f, attrs)
            # the maps' gloss program (Cg in the stage IGBs): base * colour + GlossTexture (unit 1,
            # bound by each material below) * EnvmapTexture (unit 2, a cube of textures.igb, bound
            # with the program) at the eye's reflection
            state["cube"] = bound_external(f, attrs, 2)
        gloss = bound_external(f, attrs, 1)
        if gloss:
            state["gloss_tex"] = gloss
        for unit, key in ((1, "env_image"), (2, "spec_image")):
            img = bound_image(f, attrs, unit)
            if img is not None:
                state[key] = img
        if node.type == "igGeometry":
            for a in attrs:
                if a.type.startswith("igGeometryAttr"):
                    va = f.ref(a[4])
                    if va.type == "igVertexArray1_1":
                        verts = decode_vertices_1_1(f, va)
                    else:
                        verts = decode_vertices(f, va)
                    if verts is None:
                        continue
                    tris = decode_indices(f, a, len(verts["pos"]))
                    if state.get("cube") and state.get("gloss_tex"):
                        state["gloss"] = (state["gloss_tex"], state["cube"])
                    out.append({"name": f.string(node[2]), "matrix": mat, "image": image,
                                "verts": verts, "tris": tris, "state": state, "path": path})
        for child in obj_list(f, f.ref(node[7])):
            walk(child, mat, image, state, path)

    for r in roots:
        walk(r, np.eye(4, dtype=np.float32), None, {"blend": False, "blend_func": (4, 5), "movie": None})
    return f, out
