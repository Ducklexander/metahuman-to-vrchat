// Puts the imported avatar in the scene with a working VRC Avatar Descriptor and Jerry's ARKit
// face-tracking template.
//
// Decisions carried over from the original build:
//   * Eye Look uses the eye_l / eye_r bones, so idle eye movement works when VRCFaceTracking is
//     not running.
//   * VF_EyeRotation is removed from the template. The template's FX layer already drives the
//     eyeLook* blendshapes from the same parameters, and there is no menu toggle to pick one, so
//     leaving both on doubles every eye movement while tracking. The template switches eye
//     tracking to Animation while FT is active and back to Tracking when it is off, so the bone
//     Eye Look above still works when FT is off.
//   * Eyelids: only if the FBX has a combined `vrc.blink` shape (config [bake] add_vrc_blink).

using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using VRC.SDK3.Avatars.Components;
using VRC.SDKBase;

namespace Ducklexander.MetaHumanVRChat
{
    public static class AvatarSetup
    {
        public const string TemplatePrefab = "Packages/adjerry91.vrcft.templates/Prefabs/VF_ARKit_VRCFT.prefab";

        public static readonly string[] Visemes =
        {
            "vrc.v_sil", "vrc.v_PP", "vrc.v_FF", "vrc.v_TH", "vrc.v_DD", "vrc.v_kk", "vrc.v_CH", "vrc.v_SS",
            "vrc.v_nn", "vrc.v_RR", "vrc.v_aa", "vrc.v_E", "vrc.v_ih", "vrc.v_oh", "vrc.v_ou",
        };

        // Measured on my avatar: the view point sits this far in front of the midpoint between the
        // eye bones (the bones are at the eyeball centres, the camera belongs at the cornea).
        // (my original descriptor: z 0.0926 vs eye midpoint z 0.0806).
        static readonly Vector3 ViewOffsetFromEyes = new Vector3(0f, 0f, 0.012f);

        public static GameObject SetUp(string fbxPath, Material[] slotMaterials, bool addTemplate = true)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
            var root = (GameObject)PrefabUtility.InstantiatePrefab(model);
            root.name = Path.GetFileNameWithoutExtension(fbxPath);
            Undo.RegisterCreatedObjectUndo(root, "Set up MetaHuman avatar");

            var body = FindBody(root);
            if (body == null)
            {
                Debug.LogError("[MH2VRC] No SkinnedMeshRenderer named 'Body'. Jerry's templates need that exact name.");
                return root;
            }
            if (slotMaterials != null && slotMaterials.Length == body.sharedMaterials.Length)
                body.sharedMaterials = slotMaterials;

            // Not `??`: Unity's overloaded null check does not apply to the null-coalescing operator.
            var descriptor = root.GetComponent<VRCAvatarDescriptor>();
            if (descriptor == null) descriptor = root.AddComponent<VRCAvatarDescriptor>();
            var animator = root.GetComponent<Animator>();
            var leftEye = animator != null ? animator.GetBoneTransform(HumanBodyBones.LeftEye) : null;
            var rightEye = animator != null ? animator.GetBoneTransform(HumanBodyBones.RightEye) : null;

            if (leftEye != null && rightEye != null)
            {
                var mid = (leftEye.position + rightEye.position) * 0.5f;
                descriptor.ViewPosition = root.transform.InverseTransformPoint(mid) + ViewOffsetFromEyes;
            }

            descriptor.lipSync = VRC_AvatarDescriptor.LipSyncStyle.VisemeBlendShape;
            descriptor.VisemeSkinnedMesh = body;
            descriptor.VisemeBlendShapes = (string[])Visemes.Clone();

            if (leftEye != null && rightEye != null)
            {
                descriptor.enableEyeLook = true;
                var eye = descriptor.customEyeLookSettings;
                eye.leftEye = leftEye;
                eye.rightEye = rightEye;
                // Offsets from the rest orientation: up 15, down 12, left/right 16 degrees.
                eye.eyesLookingStraight = Pair(leftEye, rightEye, Quaternion.identity);
                eye.eyesLookingUp = Pair(leftEye, rightEye, Quaternion.Euler(-15f, 0f, 0f));
                eye.eyesLookingDown = Pair(leftEye, rightEye, Quaternion.Euler(12f, 0f, 0f));
                eye.eyesLookingLeft = Pair(leftEye, rightEye, Quaternion.Euler(0f, -16f, 0f));
                eye.eyesLookingRight = Pair(leftEye, rightEye, Quaternion.Euler(0f, 16f, 0f));

                var blink = body.sharedMesh.GetBlendShapeIndex("vrc.blink");
                if (blink >= 0)
                {
                    eye.eyelidType = VRCAvatarDescriptor.EyelidType.Blendshapes;
                    eye.eyelidsSkinnedMesh = body;
                    eye.eyelidsBlendshapes = new[] { blink, -1, -1 };
                }
                else
                {
                    eye.eyelidType = VRCAvatarDescriptor.EyelidType.None;
                }
                descriptor.customEyeLookSettings = eye;
            }

            if (addTemplate) AddTemplate(root);
            EditorUtility.SetDirty(descriptor);
            Selection.activeGameObject = root;
            return root;
        }

        static VRCAvatarDescriptor.CustomEyeLookSettings.EyeRotations Pair(Transform left, Transform right, Quaternion delta)
        {
            return new VRCAvatarDescriptor.CustomEyeLookSettings.EyeRotations
            {
                linked = false,
                left = left.localRotation * delta,
                right = right.localRotation * delta,
            };
        }

        public static SkinnedMeshRenderer FindBody(GameObject root)
        {
            foreach (var smr in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                if (smr.name == "Body") return smr;
            return null;
        }

        public static GameObject AddTemplate(GameObject root)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(TemplatePrefab);
            if (prefab == null)
            {
                Debug.LogWarning($"[MH2VRC] {TemplatePrefab} not found. Install Jerry's VRCFT Templates through VCC, then run setup again or drag the ARKit template onto the avatar yourself.");
                return null;
            }
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, root.transform);
            // Removing a child of a prefab instance requires unpacking it first.
            PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            foreach (var t in instance.GetComponentsInChildren<Transform>(true))
            {
                if (t != null && t.name == "VF_EyeRotation")
                {
                    Object.DestroyImmediate(t.gameObject);
                    break;
                }
            }
            return instance;
        }

        public static List<Transform> FindEyeRotationObjects(GameObject root)
        {
            var found = new List<Transform>();
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == "VF_EyeRotation") found.Add(t);
            return found;
        }
    }
}
