// Creates the seven Poiyomi Toon materials from MaterialPresets.json.
//
// The presets are the final, tuned materials from my avatar, minus anything equal to the shader
// default. Four of the values matter far more than the rest; they are Poiyomi defaults tuned for
// toon avatars that make a realistic one ignore world lighting:
//   _LightingIgnoreAmbientColor 1 -> 0     shadowed areas otherwise take the direct light colour
//   _LightingCastedShadows      0 -> 1     world shadows otherwise never land on the avatar
//   _LightingIndirectUsesNormals 0 -> 0.333 ambient otherwise has no direction at all
//   _LightingCap                1 -> 2.5   bright worlds otherwise cannot brighten the avatar
// And one trap: _DetailNormalMap does nothing unless _DetailEnabled = 1. Without it, Poiyomi's
// lock step decides the texture is unused and strips it.

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Ducklexander.MetaHumanVRChat
{
    public static class MaterialBuilder
    {
        public const string PresetPath = "Packages/com.ducklexander.metahuman-vrchat/Editor/MaterialPresets.json";

        // Slot order of the FBX from the Blender pipeline.
        public static readonly string[] SlotOrder =
            { "Skin_Head", "Skin_Body", "Eye_L", "Eye_R", "Teeth_Tongue", "EyeEdge", "Hair" };

        [Serializable] class TextureEntry { public string property; public string file; public float[] scale; public float[] offset; }
        [Serializable] class FloatEntry { public string property; public float value; }
        [Serializable] class ColorEntry { public string property; public float[] value; }
        [Serializable] class MaterialEntry
        {
            public string name; public int renderQueue; public string renderType; public string[] keywords;
            public TextureEntry[] textures; public FloatEntry[] floats; public ColorEntry[] colors;
        }
        [Serializable] class PresetFile { public string shader; public string poiyomiVersion; public MaterialEntry[] materials; }

        static PresetFile LoadPresets()
        {
            var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(PresetPath);
            if (asset == null) throw new FileNotFoundException(PresetPath);
            return JsonUtility.FromJson<PresetFile>(asset.text);
        }

        public static Dictionary<string, Material> CreateMaterials(string texturesFolder, string materialsFolder)
        {
            var presets = LoadPresets();
            var shader = Shader.Find(presets.shader);
            if (shader == null)
                throw new InvalidOperationException($"Shader '{presets.shader}' not found. Install Poiyomi Toon {presets.poiyomiVersion} through VCC first.");

            if (!AssetDatabase.IsValidFolder(materialsFolder))
            {
                var parent = Path.GetDirectoryName(materialsFolder).Replace('\\', '/');
                AssetDatabase.CreateFolder(parent, Path.GetFileName(materialsFolder));
            }

            var textures = new Dictionary<string, Texture>(StringComparer.OrdinalIgnoreCase);
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { texturesFolder }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                textures[Path.GetFileName(path)] = AssetDatabase.LoadAssetAtPath<Texture>(path);
            }

            var created = new Dictionary<string, Material>();
            foreach (var entry in presets.materials)
            {
                var path = $"{materialsFolder}/{entry.name}.mat";
                var material = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (material == null)
                {
                    material = new Material(shader) { name = entry.name };
                    AssetDatabase.CreateAsset(material, path);
                }
                else
                {
                    material.shader = shader;
                }

                foreach (var f in entry.floats)
                    if (material.HasProperty(f.property)) material.SetFloat(f.property, f.value);
                foreach (var c in entry.colors)
                    if (material.HasProperty(c.property) && c.value != null && c.value.Length == 4)
                        material.SetColor(c.property, new Color(c.value[0], c.value[1], c.value[2], c.value[3]));

                var missing = new List<string>();
                foreach (var t in entry.textures)
                {
                    if (!material.HasProperty(t.property)) continue;
                    if (!textures.TryGetValue(t.file, out var texture) || texture == null)
                    {
                        missing.Add(t.file);
                        continue;
                    }
                    material.SetTexture(t.property, texture);
                    material.SetTextureScale(t.property, new Vector2(t.scale[0], t.scale[1]));
                    material.SetTextureOffset(t.property, new Vector2(t.offset[0], t.offset[1]));
                }

                material.shaderKeywords = entry.keywords;
                material.renderQueue = entry.renderQueue;
                if (!string.IsNullOrEmpty(entry.renderType)) material.SetOverrideTag("RenderType", entry.renderType);
                // A fresh material must start unlocked; Poiyomi locks it on upload.
                if (material.HasProperty("_ShaderOptimizerEnabled")) material.SetFloat("_ShaderOptimizerEnabled", 0f);

                EditorUtility.SetDirty(material);
                created[entry.name] = material;
                if (missing.Count > 0)
                    Debug.LogWarning($"[MH2VRC] {entry.name}: textures not found in {texturesFolder}: {string.Join(", ", missing)}");
            }
            AssetDatabase.SaveAssets();
            return created;
        }

        public static Material[] InSlotOrder(IDictionary<string, Material> materials)
        {
            var result = new Material[SlotOrder.Length];
            for (var i = 0; i < SlotOrder.Length; i++)
                materials.TryGetValue(SlotOrder[i], out result[i]);
            return result;
        }
    }
}
