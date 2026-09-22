using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Ducklexander.MetaHumanVRChat
{
    public static class Menu
    {
        const string Root = "Tools/MetaHuman to VRChat/";

        [MenuItem(Root + "Set Up Avatar (select the FBX)", priority = 1)]
        static void SetUpAll()
        {
            var fbx = SelectedFbx();
            if (fbx == null) return;
            if (!EditorUtility.DisplayDialog("MetaHuman to VRChat",
                    "This applies the import settings (the FBX reimport takes several minutes), creates the Poiyomi materials and places the avatar in the open scene.",
                    "Start", "Cancel"))
                return;
            RunImportSettings(fbx);
            RunMaterials(fbx);
            RunSceneSetup(fbx);
        }

        [MenuItem(Root + "Check Before Upload (select the avatar)", priority = 20)]
        static void Check()
        {
            var root = Selection.activeGameObject;
            if (root == null)
            {
                EditorUtility.DisplayDialog("MetaHuman to VRChat", "Select the avatar root in the Hierarchy first.", "OK");
                return;
            }
            ShowResults(root);
        }

        [MenuItem(Root + "Lock Poiyomi Materials (select the avatar)", priority = 21)]
        static void Lock()
        {
            var root = Selection.activeGameObject;
            if (root == null) return;
            var materials = root.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Where(m => m != null).Distinct();
            var ok = PreflightCheck.LockPoiyomi(materials);
            Debug.Log($"[MH2VRC] Lock {(ok ? "finished" : "failed")}.");
            ShowResults(root);
        }

        [MenuItem(Root + "Advanced/1. Apply Import Settings (select the FBX)", priority = 101)]
        static void ApplyImportSettings() { var fbx = SelectedFbx(); if (fbx != null) RunImportSettings(fbx); }

        [MenuItem(Root + "Advanced/2. Create Poiyomi Materials (select the FBX)", priority = 102)]
        static void CreateMaterials() { var fbx = SelectedFbx(); if (fbx != null) RunMaterials(fbx); }

        [MenuItem(Root + "Advanced/3. Place Avatar in Scene (select the FBX)", priority = 103)]
        static void SetUpAvatar() { var fbx = SelectedFbx(); if (fbx != null) RunSceneSetup(fbx); }

        static string SelectedFbx()
        {
            var fbx = ImportSettings.SelectedModelPaths().FirstOrDefault();
            if (fbx == null)
                EditorUtility.DisplayDialog("MetaHuman to VRChat", "Select the avatar FBX in the Project window first.", "OK");
            return fbx;
        }

        static void RunImportSettings(string fbx)
        {
            var textures = ImportSettings.TexturesFolderFor(fbx);
            var count = ImportSettings.ApplyToTextures(textures);
            Debug.Log($"[MH2VRC] Texture settings applied to {count} textures in {textures}.");
            Debug.Log($"[MH2VRC] Reimporting {fbx}. With Blend Shape Normals = Import this takes several minutes; Unity is busy, not frozen.");
            ImportSettings.ApplyToModel(fbx);
            Debug.Log($"[MH2VRC] Import settings applied to {fbx}.");
        }

        static void RunMaterials(string fbx)
        {
            var materials = MaterialBuilder.CreateMaterials(ImportSettings.TexturesFolderFor(fbx), MaterialsFolderFor(fbx));
            Debug.Log($"[MH2VRC] Created or updated {materials.Count} materials in {MaterialsFolderFor(fbx)}.");
        }

        static void RunSceneSetup(string fbx)
        {
            var folder = MaterialsFolderFor(fbx);
            var materials = MaterialBuilder.SlotOrder
                .Select(n => AssetDatabase.LoadAssetAtPath<Material>($"{folder}/{n}.mat")).ToArray();
            var root = AvatarSetup.SetUp(fbx, materials.All(m => m != null) ? materials : null);
            ShowResults(root);
        }

        public static string MaterialsFolderFor(string fbxPath) =>
            Path.GetDirectoryName(fbxPath).Replace('\\', '/') + "/Materials";

        static void ShowResults(GameObject root)
        {
            var results = PreflightCheck.Run(root);
            foreach (var r in results)
            {
                var line = $"[MH2VRC] {r}";
                if (r.severity == Severity.Error) Debug.LogError(line);
                else if (r.severity == Severity.Warning) Debug.LogWarning(line);
                else Debug.Log(line);
            }
            CheckWindow.Show(root.name, results);
        }
    }

    public class CheckWindow : EditorWindow
    {
        string avatarName;
        List<CheckResult> results = new List<CheckResult>();
        Vector2 scroll;

        public static void Show(string avatar, List<CheckResult> results)
        {
            var window = GetWindow<CheckWindow>("MetaHuman Check");
            window.avatarName = avatar;
            window.results = results;
            window.Repaint();
        }

        void OnGUI()
        {
            var errors = results.Count(r => r.severity == Severity.Error);
            var warnings = results.Count(r => r.severity == Severity.Warning);
            EditorGUILayout.LabelField(avatarName ?? "", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox(errors == 0 ? $"No blocking problems. {warnings} warning(s)." : $"{errors} error(s) must be fixed before upload.",
                errors == 0 ? MessageType.Info : MessageType.Error);
            scroll = EditorGUILayout.BeginScrollView(scroll);
            foreach (var r in results)
            {
                var type = r.severity == Severity.Error ? MessageType.Error
                    : r.severity == Severity.Warning ? MessageType.Warning : MessageType.None;
                EditorGUILayout.HelpBox((r.severity == Severity.Ok ? "OK  " : "") + r.message, type);
            }
            EditorGUILayout.EndScrollView();
        }
    }
}
