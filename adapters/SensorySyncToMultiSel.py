#!/usr/bin/env python3
"""
Single-class parser/converter: 360 video analysis JSON -> MultiSEL (XML).

Uso como biblioteca:
    from convert_json_to_multisel import MultiSelParser

    parser = MultiSelParser(author="Teste", year="2024")
    xml_str = parser.convert(effects_data, video_src="Pão de Açúcar 360.mp4")

Uso via CLI:
    python convert_json_to_multisel.py examples/output-pao.json -o output.xml --video "video.mp4"
"""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

class MultiSelParser:
    """Converte o JSON de análise de vídeo 360 (efeitos/keyframes) para MultiSEL XML."""

    def __init__(
        self,
        project_id: str = "Project-1",
        title: str = "MultiSEL for AMUSE VR",
        author: str = "",
        year: str = "",
        scene_id: str = "scene 1",
        radius: float = 5.0,
        fps: float = 1.0,
        time_unit: str = "seconds",  # "seconds" | "frames"
    ):
        self.project_id = project_id
        self.title = title
        self.author = author
        self.year = str(year)
        self.scene_id = scene_id
        self.radius = radius
        self.fps = fps
        self.time_unit = time_unit

    # ----------------------------
    # Public API
    # ----------------------------

    def convert(
        self,
        source: Any,
        video_src: str = "video.mp4",
        video_duration: float | None = None,
        output_path: str | None = None,
    ) -> str:
        """Converte a entrada em XML MultiSEL e retorna a string XML.

        source pode ser:
        - caminho (str/Path) para um arquivo JSON
        - lista de efeitos (formato do output-pao.json)
        - dict contendo a lista em chaves comuns (effects, data, result, output, annotations)
        """
        effects_data = self._extract_effects(self._load(source))
        root = self._build_multisel(effects_data, video_src=video_src, video_duration=video_duration)
        xml_str = self._to_string(root)
        if output_path:
            Path(output_path).write_text(xml_str, encoding="utf-8")
        return xml_str

    # ----------------------------
    # Input handling
    # ----------------------------

    def _load(self, source: Any) -> Any:
        if isinstance(source, (str, Path)):
            return json.loads(Path(source).read_text(encoding="utf-8"))
        if hasattr(source, "read"):
            return json.load(source)
        return source

    def _extract_effects(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Formato simples: {"effects": [...]} ou variações
            for key in ("effects", "data", "result", "output", "annotations"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    for subkey in ("effects", "data", "result", "items"):
                        subvalue = value.get(subkey)
                        if isinstance(subvalue, list):
                            return subvalue
            # Formato modules_status do SensorySynch: {"sunLocalization": {"response": {"0":[...]}}}
            normalized = self._normalize_modules_status(data)
            if normalized:
                return normalized
        raise ValueError("Entrada inválida: esperado array de efeitos ou objeto contendo a lista de efeitos.")

    def _normalize_modules_status(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Converte o status por módulo do SensorySynch para a lista de efeitos com keyframes."""
        module_to_effect = {
            "sunLocalization": "Heat",
            "fireLocalization": "Heat",
            "effectLocalization": "Heat",
            "sceneUnderstanding": "Heat",
        }
        detection_to_effect = {
            "sun": "Heat",
            "fire": "Heat",
            "heat": "Heat",
            "wind": "Wind",
            "scent": "Scent",
            "vibration": "Vibration",
            "light": "Light",
        }

        effects: list[dict[str, Any]] = []
        for module_name, module_data in data.items():
            response = None
            if isinstance(module_data, dict) and "response" in module_data:
                response = module_data.get("response")
            elif isinstance(module_data, dict) and all(str(k).isdigit() for k in module_data.keys()):
                response = module_data
            if not isinstance(response, dict):
                continue

            # Agrupa detecções por (tipo, índice na lista do frame) em trilhas temporais
            tracks: dict[tuple[str, int], dict[str, Any]] = {}
            for time_key in sorted(response.keys(), key=lambda k: float(k)):
                detections = response.get(time_key) or []
                if not isinstance(detections, list):
                    continue
                for idx, det in enumerate(detections):
                    if not isinstance(det, dict) or not det:
                        continue
                    det_type = next(iter(det.keys()))
                    payload = det.get(det_type) or {}
                    if not isinstance(payload, dict):
                        continue
                    center = payload.get("centerPoint") or {}
                    if "lat" not in center or "lon" not in center:
                        # fallback: aceita coordenadas já em x/y/z
                        if not all(k in payload for k in ("x", "y", "z")):
                            continue
                    key = (str(det_type), idx)
                    if key not in tracks:
                        eff_type = detection_to_effect.get(str(det_type).lower(), module_to_effect.get(module_name, "Heat"))
                        tracks[key] = {"effectType": eff_type, "keyframes": {}}
                    kf: dict[str, Any] = {
                        "centerPoint": {
                            "lat": float(center.get("lat", 0.0) or 0.0),
                            "lon": float(center.get("lon", 0.0) or 0.0),
                        },
                        "intensity": payload.get("intensity", "50"),
                    }
                    if "x" in payload and "y" in payload and "z" in payload:
                        kf["xyz"] = {
                            "x": float(payload.get("x", 0.0) or 0.0),
                            "y": float(payload.get("y", 0.0) or 0.0),
                            "z": float(payload.get("z", 0.0) or 0.0),
                        }
                    if "size" in payload:
                        kf["size"] = payload.get("size")
                    tracks[key]["keyframes"][str(time_key)] = kf

            # Quebra trilhas em segmentos quando há lacunas de tempo (> 1 unidade)
            for track in tracks.values():
                kfs = track["keyframes"]
                if not kfs:
                    continue
                sorted_times = sorted(kfs.keys(), key=lambda k: float(k))
                segments: list[dict[str, Any]] = []
                current: dict[str, Any] = {}
                prev_t: float | None = None
                for tk in sorted_times:
                    t = float(tk)
                    if prev_t is not None and t - prev_t > 1.0:
                        if current:
                            segments.append(current)
                        current = {}
                    current[tk] = kfs[tk]
                    prev_t = t
                if current:
                    segments.append(current)
                for seg in segments:
                    effects.append({"effectType": track["effectType"], "keyframes": seg})

        return effects

    # ----------------------------
    # Build XML
    # ----------------------------

    def _build_multisel(
        self,
        effects_data: Iterable[dict[str, Any]],
        *,
        video_src: str,
        video_duration: float | None,
    ) -> ET.Element:
        multisel = ET.Element(
            "multisel",
            {"id": self.project_id, "title": self.title, "xmlns": "DefaultProfile"},
        )

        head = ET.SubElement(multisel, "head")
        ET.SubElement(head, "meta", {"name": "author", "value": self.author})
        ET.SubElement(head, "meta", {"name": "year", "value": self.year})

        parsed_effects, max_end = self._parse_effects(effects_data)
        duration = video_duration if video_duration is not None else max_end

        body = ET.SubElement(multisel, "body", {"primaryComponent": self.scene_id})
        scene_suffix = self._scene_suffix(self.scene_id)
        video_id = f"video360_{scene_suffix}"
        scene = ET.SubElement(body, "scene", {"id": self.scene_id, "primaryComponent": video_id})

        scene.append(ET.Comment("Mídias e Efeitos Sensoriais desta cena"))
        media = ET.SubElement(scene, "media", {"id": video_id, "src": video_src, "type": "video"})
        ET.SubElement(media, "property", {"name": "duration", "value": self._fmt_num(duration)})
        ET.SubElement(media, "property", {"name": "background", "value": "true"})
        ET.SubElement(media, "property", {"name": "loop", "value": "false"})
        ET.SubElement(media, "property", {"name": "volume", "value": "1"})
        ET.SubElement(media, "property", {"name": "mute", "value": "false"})

        type_counters: dict[str, int] = {}
        relation_specs: list[tuple[str, float]] = []

        for eff in parsed_effects:
            prefix = self._effect_id_prefix(eff["type_name"])
            type_counters[prefix] = type_counters.get(prefix, 0) + 1
            eff_id = f"{prefix}-{type_counters[prefix]}_{scene_suffix}"

            effect_el = ET.SubElement(scene, "effect", {"id": eff_id, "type": eff["type_name"]})
            ET.SubElement(effect_el, "property", {"name": "duration", "value": self._fmt_num(eff["duration"])})
            ET.SubElement(effect_el, "property", {"name": "x", "value": self._fmt_num(eff["x"])})
            ET.SubElement(effect_el, "property", {"name": "y", "value": self._fmt_num(eff["y"])})
            ET.SubElement(effect_el, "property", {"name": "z", "value": self._fmt_num(eff["z"])})
            ET.SubElement(effect_el, "property", {"name": "loop", "value": "false"})
            ET.SubElement(effect_el, "property", {"name": "intensity", "value": self._fmt_num(eff["intensity"])})
            relation_specs.append((eff_id, eff["start"]))

        scene.append(ET.Comment("Relações desta cena"))
        self._add_relations(scene, self.scene_id, video_id, relation_specs)
        self._indent(multisel)
        return multisel

    def _parse_effects(self, effects_data: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
        parsed: list[dict[str, Any]] = []
        max_end = 0.0
        for eff in effects_data:
            keyframes = eff.get("keyframes") or {}
            if not keyframes:
                continue

            times = sorted(float(k) for k in keyframes.keys())
            start_t = times[0]
            end_t = times[-1]
            if self.time_unit == "frames":
                start_t /= self.fps
                end_t /= self.fps
            duration = max(0.0, end_t - start_t)
            max_end = max(max_end, end_t)

            rep = self._pick_position_keyframe(keyframes) or {}
            if "xyz" in rep and isinstance(rep["xyz"], dict):
                xyz = rep["xyz"]
                x = float(xyz.get("x", 0.0) or 0.0)
                y = float(xyz.get("y", 0.0) or 0.0)
                z = float(xyz.get("z", 0.0) or 0.0)
            else:
                center = rep.get("centerPoint") or {}
                lat = float(center.get("lat", 0.0) or 0.0)
                lon = float(center.get("lon", 0.0) or 0.0)
                x, y, z = self._latlon_to_xyz(lat, lon, self.radius)

            parsed.append(
                {
                    "type_name": self._effect_type_name(eff.get("effectType", "Effect")),
                    "start": start_t,
                    "duration": duration,
                    "x": x,
                    "y": y,
                    "z": z,
                    "intensity": self._normalize_intensity((rep or {}).get("intensity", 1.0)),
                }
            )
        return parsed, max_end

    def _add_relations(
        self,
        scene: ET.Element,
        scene_id: str,
        video_id: str,
        relation_specs: list[tuple[str, float]],
    ) -> None:
        rel_index = 1

        def add_relation(rtype: str, primary: str, secondary: str, delay: float | None = None) -> None:
            nonlocal rel_index
            attrs = {"id": f"Relation-{rel_index}", "type": rtype}
            if delay is not None and abs(delay) > 1e-9:
                attrs["delay"] = self._fmt_num(delay)
            rel = ET.SubElement(scene, "relation", attrs)
            ET.SubElement(rel, "primary", {"component": primary})
            ET.SubElement(rel, "secondary", {"component": secondary})
            rel_index += 1

        add_relation("finishes", scene_id, video_id)
        for eff_id, start_t in relation_specs:
            add_relation("starts", scene_id, eff_id, delay=start_t)
            add_relation("finishes", scene_id, eff_id)

    # ----------------------------
    # Helpers
    # ----------------------------

    @staticmethod
    def _scene_suffix(scene_id: str) -> str:
        return "s" + scene_id[len("scene "):].replace(" ", "") if scene_id.startswith("scene ") else scene_id.replace(" ", "")

    @staticmethod
    def _latlon_to_xyz(lat_deg: float, lon_deg: float, radius: float = 5.0) -> tuple[float, float, float]:
        lat = math.radians(lat_deg)
        lon = math.radians(lon_deg)
        x = radius * math.cos(lat) * math.sin(lon)
        y = radius * math.sin(lat)
        z = radius * math.cos(lat) * math.cos(lon)
        return x, y, z

    @staticmethod
    def _fmt_num(value: float) -> str:
        return f"{value:.7g}"

    @staticmethod
    def _normalize_intensity(raw: Any) -> float:
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return 1.0
        if val > 1.0:
            val = val / 100.0
        return max(0.0, min(1.0, val))

    @staticmethod
    def _effect_type_name(effect_type: str) -> str:
        etype = (effect_type or "Effect").strip()
        return etype if etype.endswith("Type") else f"{etype}Type"

    @staticmethod
    def _effect_id_prefix(effect_type_name: str) -> str:
        base = (effect_type_name or "Effect").replace("Type", "").strip().lower()
        return f"se{base}"

    @staticmethod
    def _pick_position_keyframe(keyframes: dict[str, Any]) -> dict[str, Any]:
        if not keyframes:
            return {}
        items = sorted(keyframes.items(), key=lambda kv: float(kv[0]))
        return items[0][1]

    @staticmethod
    def _indent(elem: ET.Element, level: int = 0) -> None:
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                MultiSelParser._indent(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            if len(elem) and (not elem[-1].tail or not elem[-1].tail.strip()):
                elem[-1].tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    @staticmethod
    def _to_string(root: ET.Element) -> str:
        body = ET.tostring(root, encoding="unicode")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


# ----------------------------
# CLI
# ----------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert 360 analysis JSON to MultiSEL XML.")
    parser.add_argument("input", help="Path to input JSON file")
    parser.add_argument("-o", "--output", help="Path to output .xml file (default: stdout)")
    parser.add_argument("--project-id", default="Project-1", help="multisel id")
    parser.add_argument("--title", default="MultiSEL for AMUSE VR", help="multisel title")
    parser.add_argument("--author", default="", help="meta author")
    parser.add_argument("--year", default="", help="meta year")
    parser.add_argument("--scene-id", default="scene 1", help="scene id")
    parser.add_argument("--video", default="video.mp4", help="video source filename/path")
    parser.add_argument("--video-duration", type=float, default=None, help="video duration (seconds); defaults to max effect end time")
    parser.add_argument("--radius", type=float, default=5.0, help="sphere radius for lat/lon to x,y,z conversion")
    parser.add_argument("--fps", type=float, default=1.0, help="frames per second when --time-unit=frames")
    parser.add_argument("--time-unit", choices=["seconds", "frames"], default="seconds", help="interpret keyframe keys as seconds or frames")
    return parser