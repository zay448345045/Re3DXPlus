#!/bin/sh
# Pack the Tokyo map the way the arcade loads it, for its morning (other_stage/c1_daytime.lua
# plus the makers' signboards of tokyo/daytime/daytime.lua) or its night (tokyo/night/night.lua):
# GroundModel (ground), ShortRangeBuildModel and LongRangeBuildModel (buildings, signs; at night
# also FlareModel, the glowing signs and windows), with the map's own textures.igb, plus
# - the "OtherLight" models lua_common/map2_common.lua adds to every Tokyo area list (blinking
#   warning lights, the animated curve arrows; at night also the searchlights),
# - the guardrails clGraphicFrame::setBarricade puts across the closed junctions (barricades.txt
#   from barricades.py), stage_common/gurdrail_daytime.igb or gurdrail_night.igb,
# - the junction arrow boards (coursearrow, shown per junction block at run time) into
#   arrows.wpk + arrows.names (arrows_night.wpk at night),
# - the sky box (SkyBoxModel) into sky.wpk (sky_night.wpk at night).
# Usage: tools/stage/pack_tokyo.sh [daytime|night] [out.wpk]
set -e
cd "$(dirname "$0")"
TIME=daytime
case "$1" in daytime|night) TIME=$1; shift ;; esac
A="../../../Wangan Midnight Maximum Tune 3DX+ (Japan)/data"
D="$A/tokyo/$TIME"
MAKERS="sk_makerkanban_C1_kandabashi sk_makerkanban_C1_shibapark sk_makerkanban_C1_shiodome
   sk_makerkanban_shinkanjo_ariake sk_makerkanban_shinkanjo_kiba sk_makerkanban_Wangan_13gouchi
   wg_makerkanban_Wangan_daikokuhuto wg_makerkanban_Wangan_kukochuo sk_makerkanban_Yokohane_shibaura
   yh_makerkanban_Yokohane_haneda yh_makerkanban_Yokohane_shioiri"
OTHER="c1_otherlight sk_otherlight wg_otherlight yh_otherlight"
if [ "$TIME" = night ]; then
  OUT="${1:-../../data/tokyo_night.wpk}"
  SUFFIX=_night
  G="sk_area01_N sk_area02_N sk_area03_N sk_area04_N sk_area05_N sk_area06_N sk_area07_N sk_area08_N
     sk_area09_N sk_area10_N sk_area11_N sk_area12_N sk_area13_N sk_area15_N sk_area16_N sk_area17_N
     sk_area18_N wg_suimen_ni wg_area01_michi_ni wg_area02_michi_ni wg_area04_michi_ni wg_area06_michi_ni
     wg_area09_michi_ni wg_area11_michi_ni wg_area12_michi_ni yh_area01_michi_ni yh_area02_michi_ni
     yh_area05_michi_ni yh_area06_michi_ni yh_area07_michi_ni yh_area08_michi_ni $MAKERS $OTHER"
  S="sk_ginza_Ns sk_shibapark10_Ns sk_kasumigaseki_N sk_edagawa_N sk_odaiba_Ns sk_oi_Ns sk_rb_N
     wg_area01_building_ni wg_area02_building_ni wg_area04_building_ni wg_area09_building_ni
     wg_area11_building_ni wg_area12_building_ni yh_area01_building_ni yh_area02_building_ni
     yh_area05_building_ni yh_area06_building_ni yh_area07_building_ni yh_area08_building_ni"
  L="sk_area14_N sk_ginza_Nl sk_shibapark10_Nl sk_odaiba_N_beam sk_odaiba_Nl sk_oi_Nl sk_searchlight
     sk_ginza_glow sk_edagawa_glow sk_kasumigaseki_glow sk_shibapark10_glow sk_rb_glow sk_oi_glow
     sk_odaiba_glow sk_tower_N sk_ginza_sign sk_shibapark10_sign sk_kasumigaseki_sign sk_oi_sign
     sk_edagawa_sign sk_rb_sign wg_area01_kanban_ni wg_area02_kanban_ni wg_area04_kanban_ni
     wg_area06_kanban_ni wg_area09_kanban_ni wg_area11_kanban_ni yh_area01_kanban_ni yh_area02_kanban_ni
     yh_area05_kanban_ni yh_area06_kanban_ni yh_area07_kanban_ni yh_area08_kanban_ni"
  SKY="sk_sky1_N sk_sky2_N"
else
  OUT="${1:-../../data/tokyo.wpk}"
  SUFFIX=
  G="sk_area01_m sk_area02_m sk_area03_m sk_area04_m sk_area05_m sk_area06_m sk_area07_m sk_area08_m
     sk_area09_m sk_area10_m sk_area11_m sk_area12_m sk_area13_m sk_area15_m sk_area16_m sk_area17_m
     sk_area18_m wg_suimen_m wg_area01_michi_m wg_area02_michi_m wg_area04_michi_m wg_area06_michi_m
     wg_area09_michi_m wg_area11_michi_m wg_area12_michi_m yh_area01_michi_m yh_area02_michi_m
     yh_area05_michi_m yh_area06_michi_m yh_area07_michi_m yh_area08_michi_m $MAKERS $OTHER"
  S="sk_ginza_ms sk_shibapark10_ms sk_kasumigaseki_m sk_edagawa_m sk_odaiba_ms sk_oi_ms sk_rb_m
     wg_area01_building_m wg_area02_building_m wg_area04_building_m wg_area09_building_m
     wg_area11_building_m wg_area12_building_m wg_area01_kanban wg_area01_kanban_m wg_area02_kanban_m wg_area04_kanban_m
     wg_area06_kanban_m yh_area01_building_m yh_area02_building_m yh_area05_building_m
     yh_area06_building_m yh_area07_building_m yh_area08_building_m yh_area01_kanban_m
     yh_area02_kanban_m yh_area05_kanban_m yh_area06_kanban_m yh_area07_kanban_m yh_area08_kanban_m"
  L="sk_tower_m sk_area14_m sk_ginza_ml sk_ginza_sign sk_shibapark10_ml sk_shibapark10_sign
     sk_kasumigaseki_sign sk_odaiba_ml sk_odaiba_m_beam sk_oi_ml sk_oi_sign sk_edagawa_sign sk_rb_sign"
  SKY="sk_sky1 sk_sky2"
fi
# the buildings' textures at the arcade's own size (up to 1024): pack.py's 256 smeared the
# windows of the buildings beside the road into stripes
set -- "$OUT" --textures "$D/textures.igb" --max-tex-build 1024 \
  --place "$A/stage_common/gurdrail_$TIME.igb" barricades.txt
for f in $G; do set -- "$@" "$D/$f.igb"; done
set -- "$@" --short
for f in $S; do set -- "$@" "$D/$f.igb"; done
set -- "$@" --long
for f in $L; do set -- "$@" "$D/$f.igb"; done
python3 pack.py "$@"
DIR="$(dirname "$OUT")"
python3 pack.py "$DIR/arrows$SUFFIX.wpk" --textures "$D/textures.igb" \
  --objects "$A/coursearrow/tk_coursearrow_distribution.igb"
# the sky: one chunk, its textures at full size
set -- "$DIR/sky$SUFFIX.wpk" --textures "$D/textures.igb" --chunk 1000000 --max-tex 1024
for f in $SKY; do set -- "$@" "$D/$f.igb"; done
python3 pack.py "$@"
