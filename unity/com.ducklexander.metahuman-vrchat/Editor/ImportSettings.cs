// Import settings for the avatar FBX and the texture set produced by tools/textures.
//
// Every value here was settled by a failure in the original build:
//   useFileScale must stay ON. The FBX declares centimetres, stores metres and carries a 100x
//     node scale; fileScale 0.01 is what cancels it. Turning it off made the avatar 170 m tall.
//   Read/Write ON and Streaming Mip Maps ON are VRCSDK *errors* when off, not warnings.
//   Blend Shape Normals = Import: the FBX carries per-shape normals. It costs a slow import
//     (about 8 minutes for 172 shapes on my machine) because MikkTSpace runs once per shape.
//   Normal maps were green-flipped by tools/textures; do not flip them again here.

using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Ducklexander.MetaHumanVRChat
{
    public static class ImportSettings
    {
        public static bool ApplyToModel(string fbxPath)
        {
            var importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            if (importer == null)
            {
                Debug.LogError($"[MH2VRC] {fbxPath} is not a model.");
                return false;
            }

            importer.globalScale = 1f;
            importer.useFileScale = true;
            importer.useFileUnits = true;
            importer.importCameras = false;
            importer.importLights = false;
            importer.importVisibility = false;
            importer.importBlendShapes = true;
            importer.importBlendShapeNormals = ModelImporterNormals.Import;
            importer.importNormals = ModelImporterNormals.Import;
            importer.importTangents = ModelImporterTangents.CalculateMikk;
            importer.isReadable = true;
            importer.meshCompression = ModelImporterMeshCompression.Off;
            importer.optimizeMeshPolygons = true;
            importer.optimizeMeshVertices = true;
            importer.materialImportMode = ModelImporterMaterialImportMode.None;
            importer.importAnimation = false;
            importer.importConstraints = false;
            importer.animationType = ModelImporterAnimationType.Human;
            importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            importer.optimizeGameObjects = false;

            // One reimport. With Blend Shape Normals = Import this is the slow step.
            importer.SaveAndReimport();
            return true;
        }

        // Texture rules by file name, as written by tools/textures.
        struct Rule
        {
            public bool srgb, normal, mipmaps, repeat, alphaTransparency;
            public TextureImporterFormat format;
        }

        static Rule RuleFor(string fileName)
        {
            var name = Path.GetFileNameWithoutExtension(fileName);
            var rule = new Rule { srgb = true, mipmaps = true, format = TextureImporterFormat.BC7 };
            if (name == "Skin_ScatterLUT")
            {
                // Sampled by N.L and scattering amount; mipmaps or compression would smear it.
                rule.srgb = false;
                rule.mipmaps = false;
                rule.format = TextureImporterFormat.RGB24;
            }
            else if (name == "Skin_DetailNormal")
            {
                rule.normal = true;
                rule.srgb = false;
                rule.repeat = true;   // tiled 14x on the head, 30x on the body
                rule.format = TextureImporterFormat.BC5;
            }
            else if (name.EndsWith("_Normal"))
            {
                rule.normal = true;
                rule.srgb = false;
                rule.format = TextureImporterFormat.BC5;
            }
            else if (name.EndsWith("_Mask"))
            {
                rule.srgb = false;
            }
            else if (name.EndsWith("_Thickness"))
            {
                rule.srgb = false;
                rule.format = TextureImporterFormat.BC4;
            }
            else if (name == "Hair_BaseColor" || name == "EyeEdge_BaseColor")
            {
                rule.alphaTransparency = true;
            }
            return rule;
        }

        public static int ApplyToTextures(string folder)
        {
            var guids = AssetDatabase.FindAssets("t:Texture2D", new[] { folder });
            var changed = 0;
            AssetDatabase.StartAssetEditing();
            try
            {
                foreach (var guid in guids)
                {
                    var path = AssetDatabase.GUIDToAssetPath(guid);
                    var importer = AssetImporter.GetAtPath(path) as TextureImporter;
                    if (importer == null) continue;
                    if (ApplyToTexture(importer, path)) changed++;
                }
            }
            finally
            {
                AssetDatabase.StopAssetEditing();
            }
            return changed;
        }

        static bool ApplyToTexture(TextureImporter importer, string path)
        {
            var rule = RuleFor(path);
            importer.GetSourceTextureWidthAndHeight(out var width, out var height);
            var size = Mathf.NextPowerOfTwo(Mathf.Max(width, height, 32));

            importer.textureType = rule.normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            importer.sRGBTexture = rule.srgb;
            importer.alphaIsTransparency = rule.alphaTransparency;
            importer.mipmapEnabled = rule.mipmaps;
            importer.streamingMipmaps = rule.mipmaps;   // VRCSDK error if a mipmapped texture lacks it
            importer.wrapMode = rule.repeat ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
            importer.filterMode = FilterMode.Bilinear;
            importer.maxTextureSize = size;
            importer.textureCompression = TextureImporterCompression.CompressedHQ;
            importer.crunchedCompression = false;
            importer.compressionQuality = 100;
            importer.isReadable = false;

            var standalone = importer.GetPlatformTextureSettings("Standalone");
            standalone.overridden = true;
            standalone.maxTextureSize = size;
            standalone.format = rule.format;
            standalone.compressionQuality = 100;
            standalone.crunchedCompression = false;
            importer.SetPlatformTextureSettings(standalone);

            importer.SaveAndReimport();
            return true;
        }

        public static string TexturesFolderFor(string fbxPath)
        {
            var folder = Path.GetDirectoryName(fbxPath).Replace('\\', '/');
            var candidate = folder + "/Textures";
            return AssetDatabase.IsValidFolder(candidate) ? candidate : folder;
        }

        public static List<string> SelectedModelPaths()
        {
            var result = new List<string>();
            foreach (var obj in Selection.objects)
            {
                var path = AssetDatabase.GetAssetPath(obj);
                if (!string.IsNullOrEmpty(path) && AssetImporter.GetAtPath(path) is ModelImporter)
                    result.Add(path);
            }
            return result;
        }
    }
}
