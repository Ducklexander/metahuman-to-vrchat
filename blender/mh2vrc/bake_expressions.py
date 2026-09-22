# =============================================================================================
# MetaHuman RigLogic -> VRChat blendshape bake: the expression tables
#
# Edit the tables below and re-run `blender/run.py --from bake`; every shape is rebuilt from them.
# A new head.dna needs the full run (`--from import`).
#
# HOW THE BAKE WORKS
# ------------------
# MetaHuman expressions are ~80% skeletal (870 face joints) plus a corrective/PSD blend-shape
# layer. "New Shape From Mix" - the obvious Blender workflow - only captures the
# shape-key layer, so it would silently throw away the joint deformation that carries most of
# the expression. Instead, for each entry we:
#
#     1. zero every raw control, set this entry's controls, run RigLogic
#     2. read each mesh's EVALUATED vertex positions (shape keys + armature modifier applied)
#     3. write those absolute positions into a new shape key on the un-evaluated mesh
#
# A shape key is evaluated before the armature modifier, so as long as the face bones sit at
# rest in the exported FBX (they do - stage 07 strips them and merges their weights onto
# `head`), replaying the key reproduces the full RigLogic result exactly.
#
# CONTROL VALUES: WHERE THEY COME FROM
# ------------------------------------
# Every raw control below is a real MetaHuman `CTRL_expressions.*` channel (263 of them, read
# from head.dna). Three sources back the numbers, and each entry says which:
#
#   [scan]   Poly Hammer's bundled scan_reference pose library - FACS reference poses authored
#            against this exact rig. Extracted to <work_dir>/addon_poses_raw.json by the import stage.
#            Used verbatim wherever an ARKit shape has a 1:1 FACS counterpart.
#   [1:1]    The MetaHuman control is the same action as the ARKit/Unified shape, so the mapping
#            is the single control at 1.0.
#   [split]  MetaHuman resolves the action more finely than ARKit does (e.g. ARKit's one
#            `mouthFunnel` vs MetaHuman's upper/lower x left/right quad), so the ARKit shape is
#            all of the finer controls together. This is also what makes the Unified Expressions
#            increment possible: we bake the finer controls individually as well.
#   [interp] ARKit's shape has no exact MetaHuman counterpart and is composed. The reasoning is
#            written on the line.
#
# Epic's own PA_MetaHuman_ARKit_Mapping was the intended authority here. It is present in the UE
# project and its 52 pose names were read successfully, but UE 5.6's Python bindings expose no
# way to read a PoseAsset's or AnimSequence's curve VALUES (AnimationBlueprintLibrary is absent
# in commandlet mode and AnimationDataModel exposes only get_number_of_float_curves). See
# docs/03-blender-bake.md. The tables below are therefore rig-derived, and are validated by rendering.
#
# L/R CONVENTION - verified empirically, not assumed
# --------------------------------------------------
# The character's left eye sits at +X and the face looks toward -Y. Driving `eyeLookLeftL` moves
# that eye's pupil +8.95mm in X, i.e. toward the character's own left. So in MetaHuman naming the
# Left/Right inside eyeLook* is the DIRECTION and the trailing L/R is WHICH EYE. ARKit's
# Left/Right is the character's own side too, so:
#     eyeLookInLeft  -> eyeLookRightL   (left eye toward the nose = toward character's right)
#     eyeLookOutLeft -> eyeLookLeftL
# =============================================================================================

import json

from . import config


def _both(prefix, value=1.0, suffix=("L", "R")):
    return {f"{prefix}{s}": value for s in suffix}


def _quad(prefix, value=1.0):
    """MetaHuman's upper/lower x left/right lip quad: UL, UR, DL, DR."""
    return {f"{prefix}{s}": value for s in ("UL", "UR", "DL", "DR")}


# =============================================================================================
# TABLE 1 - ARKit 52
# The baseline set. Jerry's VRCFT Templates drive these names directly, and FoxyFace/VRCFT emit
# ARKit parameters, so this table alone makes the avatar fully face-trackable.
# =============================================================================================

ARKIT_52 = {
    # ---- brow -------------------------------------------------------------------------------
    # [scan] Brows_Lower pairs browDown with browLateral (the corrugator pulls down AND inward).
    # ARKit's browDown is that same combined action, so we keep both but let browDown lead.
    "browDownLeft": {"browDownL": 1.0, "browLateralL": 0.5},
    "browDownRight": {"browDownR": 1.0, "browLateralR": 0.5},
    "browInnerUp": _both("browRaiseIn"),                            # [split] ARKit has no L/R here
    "browOuterUpLeft": {"browRaiseOuterL": 1.0},                    # [1:1]
    "browOuterUpRight": {"browRaiseOuterR": 1.0},                   # [1:1]
    # ---- cheek ------------------------------------------------------------------------------
    # [scan] Blow = cheeks inflated; the lips balloon with them, which is why lipsBlow is included.
    "cheekPuff": {**_both("mouthCheekBlow"), **_both("mouthLipsBlow")},
    "cheekSquintLeft": {"eyeCheekRaiseL": 1.0},                     # [scan] Cheek_Raiser
    "cheekSquintRight": {"eyeCheekRaiseR": 1.0},
    # ---- eye --------------------------------------------------------------------------------
    "eyeBlinkLeft": {"eyeBlinkL": 1.0},                             # [scan] Blink
    "eyeBlinkRight": {"eyeBlinkR": 1.0},
    "eyeLookDownLeft": {"eyeLookDownL": 1.0},                       # [1:1]
    "eyeLookDownRight": {"eyeLookDownR": 1.0},
    "eyeLookInLeft": {"eyeLookRightL": 1.0},                        # see L/R note in the header
    "eyeLookInRight": {"eyeLookLeftR": 1.0},
    "eyeLookOutLeft": {"eyeLookLeftL": 1.0},
    "eyeLookOutRight": {"eyeLookRightR": 1.0},
    "eyeLookUpLeft": {"eyeLookUpL": 1.0},
    "eyeLookUpRight": {"eyeLookUpR": 1.0},
    # [interp] ARKit eyeSquint narrows the aperture from below; MetaHuman splits the inner-lid
    # contraction (eyeSquintInner) from the lower-lid raise, so both are needed to read as ARKit's.
    "eyeSquintLeft": {"eyeSquintInnerL": 1.0, "eyeLowerLidUpL": 0.6},
    "eyeSquintRight": {"eyeSquintInnerR": 1.0, "eyeLowerLidUpR": 0.6},
    "eyeWideLeft": {"eyeWidenL": 1.0},                              # [1:1] eyeWiden already lifts the upper lid
    "eyeWideRight": {"eyeWidenR": 1.0},
    # ---- jaw --------------------------------------------------------------------------------
    "jawForward": {"jawFwd": 1.0},                                  # [1:1]
    "jawLeft": {"jawLeft": 1.0},
    "jawRight": {"jawRight": 1.0},
    "jawOpen": {"jawOpen": 1.0},                                    # [scan] Jaw_Open
    # ---- mouth ------------------------------------------------------------------------------
    # [interp] ARKit mouthClose = the lips stay sealed while the jaw opens. MetaHuman's
    # lipsTogether quad is exactly that action, but it is CONDITIONAL: with the jaw shut the lips
    # are already touching, so driving it alone moves nothing (measured: 0.000 mm). It is
    # therefore baked differentially - see DIFFERENTIAL_BASE.
    "mouthClose": {"jawOpen": 1.0, **_quad("mouthLipsTogether")},
    "mouthDimpleLeft": {"mouthDimpleL": 1.0},                       # [scan] Dimpler
    "mouthDimpleRight": {"mouthDimpleR": 1.0},
    "mouthFrownLeft": {"mouthCornerDepressL": 1.0},                 # [scan] Mouth_Corner_Depressor
    "mouthFrownRight": {"mouthCornerDepressR": 1.0},
    "mouthFunnel": _quad("mouthFunnel"),                            # [split] [scan] Funneler
    "mouthLeft": {"mouthLeft": 1.0},                                # [1:1]
    "mouthRight": {"mouthRight": 1.0},
    "mouthLowerDownLeft": {"mouthLowerLipDepressL": 1.0},           # [scan] Lower_Lip_Depress
    "mouthLowerDownRight": {"mouthLowerLipDepressR": 1.0},
    # [split] MetaHuman's per-side press is upper+lower; mouthLipsPress adds the sideways squeeze.
    "mouthPressLeft": {"mouthPressUL": 1.0, "mouthPressDL": 1.0, "mouthLipsPressL": 0.5},
    "mouthPressRight": {"mouthPressUR": 1.0, "mouthPressDR": 1.0, "mouthLipsPressR": 0.5},
    # [interp] ARKit mouthPucker is the kiss shape: lips narrowed (purse) AND pushed forward
    # (towards). scan_reference/Pucker is exactly this plus cheek suck; we drop the cheek suck
    # because Unified tracks CheekSuck as its own parameter and mixing it in would double up.
    "mouthPucker": {**_quad("mouthLipsPurse"), **_quad("mouthLipsTowards", 0.6)},
    "mouthRollLower": _both("mouthLowerLipRollIn"),                 # [split]
    "mouthRollUpper": _both("mouthUpperLipRollIn"),                 # [split]
    # [interp] The ARKit "shrug" pair protrudes a lip outward/upward. MetaHuman's lipsPush is the
    # literal "push the lip out" control; the lower one also rides the chin pad, hence chinRaiseD.
    "mouthShrugLower": {**_both("mouthLipsPushD"), **_both("jawChinRaiseD", 0.5)},
    "mouthShrugUpper": _both("mouthLipsPushU"),
    "mouthSmileLeft": {"mouthCornerPullL": 1.0},                    # [scan] Lip_Corner_Puller
    "mouthSmileRight": {"mouthCornerPullR": 1.0},
    # [scan] Mouth_Stretch pairs the stretch with lipsClose - stretching alone peels the lips open.
    "mouthStretchLeft": {"mouthStretchL": 1.0, "mouthStretchLipsCloseL": 1.0},
    "mouthStretchRight": {"mouthStretchR": 1.0, "mouthStretchLipsCloseR": 1.0},
    "mouthUpperUpLeft": {"mouthUpperLipRaiseL": 1.0},               # [scan] Upper_Lip_Raiser
    "mouthUpperUpRight": {"mouthUpperLipRaiseR": 1.0},
    # ---- nose -------------------------------------------------------------------------------
    # [scan] Nose_Wrinkler drives both wrinkle bands; the brow/lip parts of that pose are dropped
    # because ARKit tracks them as separate parameters.
    "noseSneerLeft": {"noseWrinkleL": 1.0, "noseWrinkleUpperL": 1.0},
    "noseSneerRight": {"noseWrinkleR": 1.0, "noseWrinkleUpperR": 1.0},
    # ---- tongue -----------------------------------------------------------------------------
    # [1:1] Deliberately no jawOpen: VRChat blends shapes additively, so the jaw must stay the
    # jawOpen shape's job or the two would fight.
    "tongueOut": {"tongueOut": 1.0},
}

# =============================================================================================
# TABLE 2 - Unified Expressions increment
# Only shapes that (a) exist in VRCFT's UnifiedExpressions enum, (b) are NOT already covered by
# ARKit above, and (c) the MetaHuman rig can actually produce. Names follow VRCFT's PascalCase.
# Anything the rig cannot do is listed in UNSUPPORTED_UNIFIED below rather than faked.
# =============================================================================================

UNIFIED_EXTRA = {
    # ---- brow: ARKit has no pinch, and Unified separates it from the lowerer ------------------
    "BrowPinchLeft": {"browLateralL": 1.0},
    "BrowPinchRight": {"browLateralR": 1.0},
    # ---- eye: pupil dilation is a real MetaHuman control ---------------------------------------
    "EyeDilationLeft": {"eyePupilWideL": 1.0},
    "EyeDilationRight": {"eyePupilWideR": 1.0},
    "EyeConstrictLeft": {"eyePupilNarrowL": 1.0},
    "EyeConstrictRight": {"eyePupilNarrowR": 1.0},
    # ---- nose: ARKit collapses all nostril motion into noseSneer --------------------------------
    "NasalDilationLeft": {"noseNostrilDilateL": 1.0},
    "NasalDilationRight": {"noseNostrilDilateR": 1.0},
    "NasalConstrictLeft": {"noseNostrilCompressL": 1.0},
    "NasalConstrictRight": {"noseNostrilCompressR": 1.0},
    # ---- cheek: ARKit's cheekPuff is symmetric only ---------------------------------------------
    "CheekPuffLeft": {"mouthCheekBlowL": 1.0, "mouthLipsBlowL": 1.0},
    "CheekPuffRight": {"mouthCheekBlowR": 1.0, "mouthLipsBlowR": 1.0},
    "CheekSuckLeft": {"mouthCheekSuckL": 1.0},
    "CheekSuckRight": {"mouthCheekSuckR": 1.0},
    # ---- jaw: not in ARKit at all ---------------------------------------------------------------
    "JawBackward": {"jawBack": 1.0},
    "JawClench": _both("jawClench"),
    # [interp] MetaHuman has no control that raises the mandible above neutral - jawOpen only
    # opens. But RigLogic accepts NEGATIVE raw control values and extrapolates: jawOpen = -0.3
    # renders a clean raised mandible with the chin pushed up (9.0 mm, verified by render).
    # -1.0 was also tested and mangles the lips, so the magnitude is deliberately capped here.
    "JawMandibleRaise": {"jawOpen": -0.3},
    # [interp] Unified's corner suck. MetaHuman rolls the lips in as whole upper/lower bands, so
    # the corner-specific part comes from mouthCornerNarrow and the roll is added at partial
    # strength on that side only.
    "LipSuckCornerLeft": {"mouthCornerNarrowL": 1.0, "mouthUpperLipRollInL": 0.6, "mouthLowerLipRollInL": 0.6},
    "LipSuckCornerRight": {"mouthCornerNarrowR": 1.0, "mouthUpperLipRollInR": 0.6, "mouthLowerLipRollInR": 0.6},
    # ---- lip suck / funnel / pucker, split four ways (ARKit has one shape for each) --------------
    "LipSuckUpperLeft": {"mouthUpperLipRollInL": 1.0},
    "LipSuckUpperRight": {"mouthUpperLipRollInR": 1.0},
    "LipSuckLowerLeft": {"mouthLowerLipRollInL": 1.0},
    "LipSuckLowerRight": {"mouthLowerLipRollInR": 1.0},
    "LipFunnelUpperLeft": {"mouthFunnelUL": 1.0},
    "LipFunnelUpperRight": {"mouthFunnelUR": 1.0},
    "LipFunnelLowerLeft": {"mouthFunnelDL": 1.0},
    "LipFunnelLowerRight": {"mouthFunnelDR": 1.0},
    "LipPuckerUpperLeft": {"mouthLipsPurseUL": 1.0, "mouthLipsTowardsUL": 0.6},
    "LipPuckerUpperRight": {"mouthLipsPurseUR": 1.0, "mouthLipsTowardsUR": 0.6},
    "LipPuckerLowerLeft": {"mouthLipsPurseDL": 1.0, "mouthLipsTowardsDL": 0.6},
    "LipPuckerLowerRight": {"mouthLipsPurseDR": 1.0, "mouthLipsTowardsDR": 0.6},
    # ---- mouth shift / deepen / corner --------------------------------------------------------
    "MouthUpperDeepenLeft": {"noseNasolabialDeepenL": 1.0},
    "MouthUpperDeepenRight": {"noseNasolabialDeepenR": 1.0},
    "MouthUpperLeft": {"mouthUpperLipShiftLeft": 1.0},
    "MouthUpperRight": {"mouthUpperLipShiftRight": 1.0},
    "MouthLowerLeft": {"mouthLowerLipShiftLeft": 1.0},
    "MouthLowerRight": {"mouthLowerLipShiftRight": 1.0},
    # Unified's CornerSlant is the corner lifting without the full smile pull.
    "MouthCornerSlantLeft": {"mouthCornerUpL": 1.0},
    "MouthCornerSlantRight": {"mouthCornerUpR": 1.0},
    "MouthTightenerLeft": {"mouthLipsTightenUL": 1.0, "mouthLipsTightenDL": 1.0},
    "MouthTightenerRight": {"mouthLipsTightenUR": 1.0, "mouthLipsTightenDR": 1.0},
    # ---- tongue: the whole reason to bake beyond ARKit ------------------------------------------
    "TongueUp": {"tongueUp": 1.0},
    "TongueDown": {"tongueDown": 1.0},
    "TongueLeft": {"tongueLeft": 1.0},
    "TongueRight": {"tongueRight": 1.0},
    "TongueRoll": {"tongueRoll": 1.0},
    "TongueBendDown": {"tongueBendDown": 1.0},
    "TongueCurlUp": {"tongueBendUp": 1.0},
    "TongueSquish": {"tonguePress": 1.0},
    "TongueFlat": {"tongueThin": 1.0},
    "TongueTwistLeft": {"tongueTwistLeft": 1.0},
    "TongueTwistRight": {"tongueTwistRight": 1.0},
    # ---- neck / throat ---------------------------------------------------------------------------
    "ThroatSwallow": {"neckSwallowPh2": 1.0, "neckSwallowPh3": 1.0},
    "NeckFlexLeft": {"neckMastoidContractL": 1.0},
    "NeckFlexRight": {"neckMastoidContractR": 1.0},
}

# Unified parameters the MetaHuman rig has no control for. Recorded so the bake report can state
# the gap instead of shipping a fake shape that never moves.
UNSUPPORTED_UNIFIED = {
    "SoftPalateClose": (
        "the soft palate is not modelled at all in the LOD0 head mesh, so there is no geometry to "
        "move - no combination of controls can fake it"
    ),
}

# =============================================================================================
# TABLE 3 - MetaHuman-native extras
# Controls with no ARKit or Unified counterpart that are still worth having: they are what makes
# this rig richer than a stock ARKit avatar, and they are usable from VRChat gesture/menu
# animations even though no tracker drives them.
# =============================================================================================

METAHUMAN_EXTRA = {
    # Also conditional: lid press only bites once the eye is already closed (see DIFFERENTIAL_BASE).
    "MH_EyeLidPressLeft": {"eyeBlinkL": 1.0, "eyeLidPressL": 1.0},
    "MH_EyeLidPressRight": {"eyeBlinkR": 1.0, "eyeLidPressR": 1.0},
    "MH_EyeUpperLidUpLeft": {"eyeUpperLidUpL": 1.0},
    "MH_EyeUpperLidUpRight": {"eyeUpperLidUpR": 1.0},
    "MH_EyeLowerLidDownLeft": {"eyeLowerLidDownL": 1.0},
    "MH_EyeLowerLidDownRight": {"eyeLowerLidDownR": 1.0},
    "MH_EyeFaceScrunchLeft": {"eyeFaceScrunchL": 1.0},
    "MH_EyeFaceScrunchRight": {"eyeFaceScrunchR": 1.0},
    "MH_EarUpLeft": {"earUpL": 1.0},
    "MH_EarUpRight": {"earUpR": 1.0},
    "MH_NoseNostrilDepressLeft": {"noseNostrilDepressL": 1.0},
    "MH_NoseNostrilDepressRight": {"noseNostrilDepressR": 1.0},
    "MH_MouthSharpCornerPullLeft": {"mouthSharpCornerPullL": 1.0},
    "MH_MouthSharpCornerPullRight": {"mouthSharpCornerPullR": 1.0},
    "MH_MouthCornerWideLeft": {"mouthCornerWideL": 1.0},
    "MH_MouthCornerWideRight": {"mouthCornerWideR": 1.0},
    "MH_MouthCornerNarrowLeft": {"mouthCornerNarrowL": 1.0},
    "MH_MouthCornerNarrowRight": {"mouthCornerNarrowR": 1.0},
    "MH_MouthCornerDownLeft": {"mouthCornerDownL": 1.0},
    "MH_MouthCornerDownRight": {"mouthCornerDownR": 1.0},
    "MH_LipsThinUpper": _both("mouthLipsThinU"),
    "MH_LipsThinLower": _both("mouthLipsThinD"),
    "MH_LipsThickUpper": _both("mouthLipsThickU"),
    "MH_LipsThickLower": _both("mouthLipsThickD"),
    "MH_UpperLipBite": _both("mouthUpperLipBite"),
    "MH_LowerLipBite": _both("mouthLowerLipBite"),
    "MH_LipsTowardsTeethUpper": _both("mouthUpperLipTowardsTeeth"),
    "MH_LipsTowardsTeethLower": _both("mouthLowerLipTowardsTeeth"),
    "MH_ChinRaiseUpper": _both("jawChinRaiseU"),
    "MH_ChinCompress": _both("jawChinCompress"),
    "MH_JawOpenExtreme": {"jawOpen": 1.0, "jawOpenExtreme": 1.0},
    "MH_NeckStretch": _both("neckStretch"),
    "MH_TongueWide": {"tongueWide": 1.0},
    "MH_TongueNarrow": {"tongueNarrow": 1.0},
    "MH_TongueThick": {"tongueThick": 1.0},
    "MH_TongueIn": {"tongueIn": 1.0},
    "MH_TongueTipUp": {"tongueTipUp": 1.0},
    "MH_TongueTipDown": {"tongueTipDown": 1.0},
}

# =============================================================================================
# TABLE 4 - VRChat visemes (vrc.v_*)
#
# All 15 are composed from Poly Hammer's bundled viseme library (extracted verbatim into
# addon_poses_raw.json), which is a phoneme set authored on this rig. Two adjustments:
#
#   * The library's tongue entries (Tongue_LNTDS / _Th / _KGY / _Rr) all sit at jawOpen 1.0
#     because they are meant to be layered over a mouth shape in an animation graph. Standalone
#     VRChat visemes need one self-contained shape, so we take only the tongue* channels from
#     them and let the mouth pose supply the jaw.
#   * vrc.v_sil is the neutral face, i.e. no controls at all - it bakes to a zero-delta shape,
#     which is what VRChat's viseme system expects for silence.
#
# TONGUE_* below are the tongue-only components lifted from those library entries.
# =============================================================================================

_TONGUE_LNTDS = {"tongueOut": 0.128, "tongueRoll": 0.086}   # visemes/23_Tongue_LNTDS
_TONGUE_TH = {"tongueOut": 0.24}                            # visemes/25_Tongue-Th
_TONGUE_KGY = {"tongueIn": 0.342}                           # visemes/25_Tongue_KGY
_TONGUE_RR = {"tongueIn": 0.533, "tonguePress": 0.845}      # visemes/26_Tongue_Rr

# The library's MBP pose is mostly `mouthLipsTogether`, which is conditional on the jaw being
# open - from a closed mouth it measured only 1.36 mm, far too weak for one of the most-used
# visemes. Adding a real lip press (the action scan_reference/Mouth_Pressor uses) gives PP the
# rolled-in, compressed look it needs while staying additive.
_PP_PRESS = _quad("mouthPress", 0.45)

VISEME_SOURCE = {
    #  vrc name        addon pose key            extra component
    "vrc.v_sil": (None, None),
    "vrc.v_PP": ("visemes/22_MBP", _PP_PRESS),
    "vrc.v_FF": ("visemes/20_FV", None),
    "vrc.v_TH": ("visemes/01_TDS-Ah", _TONGUE_TH),
    "vrc.v_DD": ("visemes/01_TDS-Ah", _TONGUE_LNTDS),
    "vrc.v_kk": ("visemes/14_KGY", _TONGUE_KGY),
    "vrc.v_CH": ("visemes/14_ChJjSh", None),
    "vrc.v_SS": ("visemes/02_TDS-Ee", None),
    "vrc.v_nn": ("visemes/02_TDS-Ee", _TONGUE_LNTDS),
    "vrc.v_RR": ("visemes/17_Rr", _TONGUE_RR),
    "vrc.v_aa": ("visemes/07_Aa", None),
    "vrc.v_E": ("visemes/06_Eh", None),
    "vrc.v_ih": ("visemes/04_Ih", None),
    "vrc.v_oh": ("visemes/09_Oh", None),
    "vrc.v_ou": ("visemes/11_Oo", None),
}

# =============================================================================================
# TABLE 5 - emotion presets for VRChat hand-gesture expressions
# Straight from Poly Hammer's bundled emotion library (again, authored on this rig). Level 3 is
# the "full" reading of each of the six basic emotions; level 4 is the extreme. A few blends are
# included because they read much better than a linear mix of two singles.
# =============================================================================================

EMOTION_SOURCE = {
    "EXP_Joy": "emotions/Joy-03_Joy",
    "EXP_Laughter": "emotions/Joy-04_Laughter",
    "EXP_Anger": "emotions/Anger-03_Anger",
    "EXP_Rage": "emotions/Anger-04_Rage",
    "EXP_Sadness": "emotions/Sadness-03_Sadness",
    "EXP_Grief": "emotions/Sadness-04_Grief",
    "EXP_Surprise": "emotions/Surprise-03_Surprise",
    "EXP_Shock": "emotions/Surprise-04_Shock",
    "EXP_Fear": "emotions/Fear-03_Fear",
    "EXP_Disgust": "emotions/Disgust-03_Disgust",
    "EXP_Amazement": "emotions/Combinations/Joy+Surprise--Amazement",
    "EXP_Disbelief": "emotions/Combinations/Disgust+Surprise--Disbelief",
}


# =============================================================================================
# DIFFERENTIAL BAKES
#
# A few MetaHuman controls are conditional correctives: they only deform the mesh when some other
# control is already engaged. Driven from neutral they measure literally 0.000 mm, which would
# ship as a dead blendshape.
#
# For these we bake  delta = evaluated(pose) - evaluated(base)  instead of the usual
# `- evaluated(rest)`. VRChat sums blendshapes, so `mouthClose` + `jawOpen` then reproduces
# "jaw open, lips sealed" exactly, which is what ARKit's mouthClose means. Applied on its own
# with the jaw shut it pulls the lips past each other - that is expected and is how ARKit avatars
# implement this shape everywhere.
# =============================================================================================

DIFFERENTIAL_BASE = {
    "mouthClose": {"jawOpen": 1.0},
    "MH_EyeLidPressLeft": {"eyeBlinkL": 1.0},
    "MH_EyeLidPressRight": {"eyeBlinkR": 1.0},
}


def build_bake_table() -> dict:
    """Flatten all five tables into one ordered {shape_name: {raw_control: value}} mapping."""
    poses = json.loads(config.get().addon_poses.read_text(encoding="utf-8"))

    table = {}
    table.update(ARKIT_52)
    table.update(UNIFIED_EXTRA)
    table.update(METAHUMAN_EXTRA)

    for name, (pose_key, extra) in VISEME_SOURCE.items():
        values = dict(poses[pose_key]["raw"]) if pose_key else {}
        if extra:
            values.update(extra)
        table[name] = values

    for name, pose_key in EMOTION_SOURCE.items():
        table[name] = dict(poses[pose_key]["raw"])

    # Optional: one combined blink for the VRC Avatar Descriptor's Eyelids -> Blendshapes slot,
    # which takes a single index. Without it the avatar does not blink when VRCFaceTracking is off.
    # Adding it here costs seconds; synthesising it in Unity with an AssetPostprocessor pushed a
    # single import from 8 minutes to more than 90 (tried and abandoned).
    if config.get().extra.get("bake", {}).get("add_vrc_blink", False):
        table["vrc.blink"] = {"eyeBlinkL": 1.0, "eyeBlinkR": 1.0}

    return table


GROUPS = {
    "ARKit52": list(ARKIT_52),
    "UnifiedExtra": list(UNIFIED_EXTRA),
    "MetaHumanExtra": list(METAHUMAN_EXTRA),
    "Visemes": list(VISEME_SOURCE),
    "Emotions": list(EMOTION_SOURCE),
}
