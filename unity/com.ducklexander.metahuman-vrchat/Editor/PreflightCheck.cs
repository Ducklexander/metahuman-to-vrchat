// Pre-upload checks for a MetaHuman avatar, plus a build hook that stops the upload if a Poiyomi
// material slipped through unlocked.
//
// Everything checked here failed silently at least once in the original build. The worst one:
// Poiyomi's automatic lock skipped Eye_L / Eye_R on one upload, the unlocked shader was not
// packed into the bundle, and the eyes rendered magenta (Hidden/InternalErrorShader) in VRChat.
// Nothing in the SDK flagged it.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using VRC.SDK3.Avatars.Components;
using VRC.SDKBase.Editor.BuildPipeline;

namespace Ducklexander.MetaHumanVRChat
{
    public enum Severity { Ok, Info, Warning, Error }

    public struct CheckResult
    {
        public Severity severity;
        public string message;
        public CheckResult(Severity s, string m) { severity = s; message = m; }
        public override string ToString() => $"[{severity}] {message}";
    }

    public static class PreflightCheck
    {
        public static readonly string[] ARKit52 =
        {
            "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
            "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
            "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft", "eyeLookDownRight", "eyeLookInLeft",
            "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight",
            "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft", "eyeWideRight",
            "jawForward", "jawLeft", "jawOpen", "jawRight",
            "mouthClose", "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft", "mouthFrownRight",
            "mouthFunnel", "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft",
            "mouthPressRight", "mouthPucker", "mouthRight", "mouthRollLower", "mouthRollUpper",
            "mouthShrugLower", "mouthShrugUpper", "mouthSmileLeft", "mouthSmileRight",
            "mouthStretchLeft", "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight",
            "noseSneerLeft", "noseSneerRight", "tongueOut",
        };

        public static List<CheckResult> Run(GameObject root)
        {
            var results = new List<CheckResult>();
            void Add(Severity s, string m) => results.Add(new CheckResult(s, m));

            var descriptor = root.GetComponent<VRCAvatarDescriptor>();
            if (descriptor == null) Add(Severity.Error, "No VRC Avatar Descriptor on the selected object.");

            var body = AvatarSetup.FindBody(root);
            if (body == null)
            {
                Add(Severity.Error, "No SkinnedMeshRenderer named 'Body'. Jerry's templates look for that exact name.");
                return results;
            }
            var mesh = body.sharedMesh;

            // ---- model importer
            var meshPath = AssetDatabase.GetAssetPath(mesh);
            if (AssetImporter.GetAtPath(meshPath) is ModelImporter importer)
            {
                if (!importer.useFileScale)
                    Add(Severity.Error, "Model import: 'Convert Units' (useFileScale) is off. The avatar will be about 100x too large. Turn it back on.");
                if (!importer.isReadable)
                    Add(Severity.Error, "Model import: Read/Write is off. VRCSDK rejects the build.");
                if (importer.importBlendShapeNormals != ModelImporterNormals.Import)
                    Add(Severity.Warning, "Model import: Blend Shape Normals is not 'Import'. The FBX carries per-shape normals; Calculate/None loses them.");
                if (importer.animationType != ModelImporterAnimationType.Human)
                    Add(Severity.Error, "Model import: Rig is not Humanoid.");
                if (importer.meshCompression != ModelImporterMeshCompression.Off)
                    Add(Severity.Warning, "Model import: mesh compression is on. It is lossy and does not improve Performance Rank.");
            }
            else
            {
                Add(Severity.Info, $"Body mesh is not an imported model ({meshPath}); importer checks skipped.");
            }

            var animator = root.GetComponent<Animator>();
            if (animator == null || animator.avatar == null || !animator.avatar.isValid || !animator.avatar.isHuman)
                Add(Severity.Error, "Animator has no valid Humanoid avatar.");

            var scale = body.transform.lossyScale;
            if (Mathf.Abs(scale.x - 100f) < 0.5f)
                Add(Severity.Info, "Body lossyScale is 100 (expected with this pipeline). Divide any PhysBone radius by 100.");

            // ---- blendshapes
            var names = new HashSet<string>(Enumerable.Range(0, mesh.blendShapeCount).Select(mesh.GetBlendShapeName));
            var missingArkit = ARKit52.Where(n => !names.Contains(n)).ToList();
            if (missingArkit.Count == 0) Add(Severity.Ok, $"ARKit 52/52 present ({mesh.blendShapeCount} blendshapes total).");
            else Add(Severity.Error, $"ARKit shapes missing ({52 - missingArkit.Count}/52): {string.Join(", ", missingArkit)}");

            var missingVisemes = AvatarSetup.Visemes.Where(n => !names.Contains(n)).ToList();
            if (missingVisemes.Count > 0) Add(Severity.Error, $"Visemes missing: {string.Join(", ", missingVisemes)}");
            if (descriptor != null)
            {
                if (descriptor.lipSync != VRC.SDKBase.VRC_AvatarDescriptor.LipSyncStyle.VisemeBlendShape || descriptor.VisemeSkinnedMesh != body)
                    Add(Severity.Warning, "Descriptor lip sync is not 'Viseme Blend Shape' on Body.");
                else if (descriptor.VisemeBlendShapes == null || !descriptor.VisemeBlendShapes.SequenceEqual(AvatarSetup.Visemes))
                    Add(Severity.Warning, "Descriptor viseme list does not map vrc.v_sil ... vrc.v_ou in order.");
                else Add(Severity.Ok, "15 visemes mapped.");

                if (!descriptor.enableEyeLook) Add(Severity.Info, "Eye Look is off: no idle eye movement when face tracking is not running.");
                if (descriptor.customEyeLookSettings.eyelidType == VRCAvatarDescriptor.EyelidType.None)
                    Add(Severity.Info, "No eyelid blink configured. The avatar will not blink without VRCFaceTracking. Re-bake with [bake] add_vrc_blink = true to fix.");
            }

            // ---- face tracking template
            var eyeRotation = AvatarSetup.FindEyeRotationObjects(root);
            var hasTemplate = root.GetComponentsInChildren<Transform>(true).Any(t => t.name.Contains("VRCFT"));
            if (!hasTemplate) Add(Severity.Warning, "No Jerry's VRCFT template found under the avatar. Face tracking will not drive anything.");
            if (eyeRotation.Count > 0)
                Add(Severity.Error, "VF_EyeRotation is present. With the ARKit template it doubles every eye movement while tracking. Delete it.");

            // ---- materials and textures
            var materials = root.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Where(m => m != null).Distinct().ToList();
            var slots = body.sharedMaterials;
            if (slots.Any(m => m == null)) Add(Severity.Error, "Body has empty material slots.");
            Add(slots.Length <= 8 ? Severity.Ok : Severity.Warning, $"{slots.Length} material slots on Body (8 or fewer keeps the material rank at Good).");

            var streamingMissing = new List<string>();
            foreach (var material in materials)
            {
                if (material.shader == null || !material.shader.isSupported)
                    Add(Severity.Error, $"{material.name}: shader missing or unsupported (renders magenta).");
                if (material.HasProperty("_DetailNormalMap") && material.GetTexture("_DetailNormalMap") != null
                    && material.HasProperty("_DetailEnabled") && material.GetFloat("_DetailEnabled") < 0.5f)
                    Add(Severity.Warning, $"{material.name}: _DetailNormalMap is set but _DetailEnabled is 0, so it does nothing and gets stripped on lock.");
                foreach (var prop in material.GetTexturePropertyNames())
                {
                    var tex = material.GetTexture(prop) as Texture2D;
                    if (tex == null) continue;
                    if (AssetImporter.GetAtPath(AssetDatabase.GetAssetPath(tex)) is TextureImporter ti && ti.mipmapEnabled && !ti.streamingMipmaps)
                        streamingMissing.Add(tex.name);
                }
                if (IsPoiyomi(material) && !IsLocked(material))
                    Add(Severity.Info, $"{material.name}: Poiyomi material not locked yet. Poiyomi locks it during the build; the build hook verifies that.");
            }
            if (streamingMissing.Count > 0)
                Add(Severity.Error, $"Mipmapped textures without Streaming Mip Maps (VRCSDK error): {string.Join(", ", streamingMissing.Distinct())}");

            // ---- rank hint
            var tris = mesh.triangles.Length / 3;
            Add(tris <= 70000 ? Severity.Ok : Severity.Info,
                tris <= 70000 ? $"{tris:N0} triangles." : $"{tris:N0} triangles: PC Performance Rank will be Very Poor (limit for Poor is 70,000). Expected for an undecimated MetaHuman head.");

            return results;
        }

        public static bool IsPoiyomi(Material m) => m.shader != null && m.HasProperty("_ShaderOptimizerEnabled");

        public static bool IsLocked(Material m)
        {
            if (!IsPoiyomi(m)) return true;
            var shaderPath = AssetDatabase.GetAssetPath(m.shader);
            return m.GetFloat("_ShaderOptimizerEnabled") > 0.5f && !shaderPath.StartsWith("Packages/", StringComparison.Ordinal);
        }

        /// Lock through Thry's ShaderOptimizer by reflection, so this package does not need a
        /// hard reference to Poiyomi's assembly.
        public static bool LockPoiyomi(IEnumerable<Material> materials)
        {
            var type = AppDomain.CurrentDomain.GetAssemblies()
                .Select(a => a.GetType("Thry.ThryEditor.ShaderOptimizer", false))
                .FirstOrDefault(t => t != null);
            var method = type?.GetMethod("SetLockedForAllMaterials", BindingFlags.Public | BindingFlags.Static);
            if (method == null)
            {
                Debug.LogError("[MH2VRC] Thry.ThryEditor.ShaderOptimizer.SetLockedForAllMaterials not found. Is Poiyomi installed?");
                return false;
            }
            var list = materials.Where(IsPoiyomi).ToList();
            return (bool)method.Invoke(null, new object[] { list, 1, false, false, false, null });
        }
    }

    /// Runs after Poiyomi's own lock step (callbackOrder 100) on the avatar copy that is about to be
    /// built, and fails the build if any Poiyomi material is still unlocked.
    ///
    /// Only for real builds (Build and Test, Build and Upload). For a build-only run the SDK's
    /// ActiveBuildType is None, VRCFury deliberately skips Poiyomi's lock step, and unlocked
    /// materials are expected, so the hook only warns.
    public class PoiyomiLockVerifier : IVRCSDKPreprocessAvatarCallback
    {
        public int callbackOrder => 10000;

        public bool OnPreprocessAvatar(GameObject avatarGameObject)
        {
            var unlocked = avatarGameObject.GetComponentsInChildren<Renderer>(true)
                .SelectMany(r => r.sharedMaterials)
                .Where(m => m != null && PreflightCheck.IsPoiyomi(m) && !PreflightCheck.IsLocked(m))
                .Select(m => m.name).Distinct().ToList();
            if (unlocked.Count == 0) return true;

            var list = string.Join(", ", unlocked);
            if (IsBuildOnly())
            {
                Debug.LogWarning($"[MH2VRC] Build-only run: Poiyomi materials are not locked ({list}). That is expected here; they must be locked by the time you test or upload.");
                return true;
            }
            Debug.LogError($"[MH2VRC] Build stopped: these Poiyomi materials are not locked and would render magenta in VRChat: {list}. "
                           + "Run Tools > MetaHuman to VRChat > Lock Poiyomi Materials, then build again.");
            return false;
        }

        /// True when the SDK reports no active test/upload build. Read by reflection because
        /// older SDKs do not have the property; on those, the check stays strict.
        static bool IsBuildOnly()
        {
            var type = Type.GetType("VRC.SDKBase.Editor.VRC_SdkBuilder, VRCSDKBase-Editor")
                       ?? AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetType("VRC.SDKBase.Editor.VRC_SdkBuilder", false)).FirstOrDefault(t => t != null);
            var prop = type?.GetProperty("ActiveBuildType", BindingFlags.Public | BindingFlags.Static);
            var value = prop?.GetValue(null);
            return value != null && value.ToString() == "None";
        }
    }
}
