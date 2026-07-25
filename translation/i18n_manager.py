#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
                        创世铭文 · GENESIS INSCRIPTION
政党名称: 海燕党
英文名称: PETREL AI PARTY
创始人: 刘海燕（LIU HAIYAN）
================================================================================
i18n_manager.py — 多语言管理

功能:
  - 首批10语言管理：中/英/西/法/阿/俄/葡/德/日/韩
  - AI初翻（模拟）+ 人工校对流程
  - 翻译记忆库（TM）+ 术语库（Glossary）
  - 多语言资源文件导出（JSON / PO / XLIFF）
================================================================================
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 语言定义
# ---------------------------------------------------------------------------

LanguageInfo = dict[str, Any]

LANGUAGES: dict[str, LanguageInfo] = {
    "zh": {
        "code": "zh",
        "name_zh": "中文",
        "name_en": "Chinese",
        "native_name": "中文",
        "direction": "ltr",
        "priority": 1,
    },
    "en": {
        "code": "en",
        "name_zh": "英文",
        "name_en": "English",
        "native_name": "English",
        "direction": "ltr",
        "priority": 2,
    },
    "es": {
        "code": "es",
        "name_zh": "西班牙语",
        "name_en": "Spanish",
        "native_name": "Español",
        "direction": "ltr",
        "priority": 3,
    },
    "fr": {
        "code": "fr",
        "name_zh": "法语",
        "name_en": "French",
        "native_name": "Français",
        "direction": "ltr",
        "priority": 4,
    },
    "ar": {
        "code": "ar",
        "name_zh": "阿拉伯语",
        "name_en": "Arabic",
        "native_name": "العربية",
        "direction": "rtl",
        "priority": 5,
    },
    "ru": {
        "code": "ru",
        "name_zh": "俄语",
        "name_en": "Russian",
        "native_name": "Русский",
        "direction": "ltr",
        "priority": 6,
    },
    "pt": {
        "code": "pt",
        "name_zh": "葡萄牙语",
        "name_en": "Portuguese",
        "native_name": "Português",
        "direction": "ltr",
        "priority": 7,
    },
    "de": {
        "code": "de",
        "name_zh": "德语",
        "name_en": "German",
        "native_name": "Deutsch",
        "direction": "ltr",
        "priority": 8,
    },
    "ja": {
        "code": "ja",
        "name_zh": "日语",
        "name_en": "Japanese",
        "native_name": "日本語",
        "direction": "ltr",
        "priority": 9,
    },
    "ko": {
        "code": "ko",
        "name_zh": "韩语",
        "name_en": "Korean",
        "native_name": "한국어",
        "direction": "ltr",
        "priority": 10,
    },
}

SUPPORTED_LANGUAGES = list(LANGUAGES.keys())
SUPPORTED_LANGUAGE_COUNT = len(SUPPORTED_LANGUAGES)


# ---------------------------------------------------------------------------
# 翻译记忆库条目
# ---------------------------------------------------------------------------


@dataclass
class TranslationMemoryEntry:
    """翻译记忆库（TM）条目"""
    source_text: str
    source_language: str
    target_text: str
    target_language: str
    context: str = ""
    confidence: float = 1.0       # 0.0 ~ 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class GlossaryEntry:
    """术语库条目"""
    source_term: str
    source_language: str
    target_term: str
    target_language: str
    domain: str = "general"       # 领域：general / tech / legal / medical
    notes: str = ""


# ---------------------------------------------------------------------------
# AI 翻译引擎（模拟）
# ---------------------------------------------------------------------------


class AITranslationEngine:
    """
    AI 初翻引擎。

    真实部署时可对接 OpenAI / DeepSeek 等翻译 API。
    当前版本使用模拟翻译，展示接口契约。
    """

    def __init__(self, model_name: str = "petrel-translate-v1"):
        self.model_name = model_name
        self._glossary: list[GlossaryEntry] = []

    def load_glossary(self, entries: list[GlossaryEntry]) -> None:
        """加载术语库"""
        self._glossary = entries

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: str = "",
    ) -> str:
        """
        AI 初翻。

        真实实现: 组装 prompt → 调用 LLM API → 返回译文。
        当前: 为测试目的生成带标记的模拟翻译。
        """
        if not text.strip():
            return ""

        # 应用术语替换
        translated = text
        for entry in self._glossary:
            if entry.source_language == source_language and entry.target_language == target_language:
                translated = translated.replace(entry.source_term, entry.target_term)

        # 模拟翻译：添加语言后缀标记便于测试
        lang_map = {
            "en": "[EN]",
            "zh": "[ZH]",
            "es": "[ES]",
            "fr": "[FR]",
            "ar": "[AR]",
            "ru": "[RU]",
            "pt": "[PT]",
            "de": "[DE]",
            "ja": "[JA]",
            "ko": "[KO]",
        }
        suffix = lang_map.get(target_language, f"[{target_language.upper()}]")
        return f"{suffix} {translated}"


# ---------------------------------------------------------------------------
# 多语言管理器
# ---------------------------------------------------------------------------


class I18nManager:
    """
    多语言管理器

    职责:
      - 管理首批 10 语言的资源文件
      - AI 初翻 + 人工校对流程编排
      - 翻译记忆库（TM）和术语库（Glossary）
      - 多语言资源文件导出（JSON / PO / XLIFF）
    """

    def __init__(
        self,
        resource_dir: str = "",
        ai_engine: Optional[AITranslationEngine] = None,
    ):
        self.resource_dir = resource_dir or os.path.join(
            os.path.dirname(__file__), "locales"
        )
        self.ai_engine = ai_engine or AITranslationEngine()
        self._translations: dict[str, dict[str, str]] = {}
        # _translations[lang_code][key] = translated_text

        self._tm: list[TranslationMemoryEntry] = []
        self._glossary: list[GlossaryEntry] = []

        # 初始化空翻译容器
        for lang in SUPPORTED_LANGUAGES:
            self._translations[lang] = {}

    # ---- 语言信息查询 ----

    def get_language_info(self, code: str) -> Optional[LanguageInfo]:
        return LANGUAGES.get(code)

    def list_languages(self) -> list[LanguageInfo]:
        langs = list(LANGUAGES.values())
        langs.sort(key=lambda x: x["priority"])
        return langs

    # ---- 翻译管理 ----

    def set_translation(self, key: str, lang: str, text: str) -> None:
        """设置单个翻译"""
        if lang not in self._translations:
            raise ValueError(f"不支持的语言: {lang}")
        self._translations[lang][key] = text

    def get_translation(self, key: str, lang: str, default: str = "") -> str:
        """获取单个翻译"""
        return self._translations.get(lang, {}).get(key, default)

    def get_all_translations(self, lang: str) -> dict[str, str]:
        """获取指定语言的全部翻译"""
        return dict(self._translations.get(lang, {}))

    def get_missing_keys(self, lang: str, reference_lang: str = "zh") -> list[str]:
        """获取指定语言中缺失的翻译键"""
        reference = self._translations.get(reference_lang, {})
        target = self._translations.get(lang, {})
        return [k for k in reference if k not in target]

    # ---- AI 初翻 ----

    def ai_translate_batch(
        self,
        keys: list[str],
        source_lang: str,
        target_lang: str,
        context: str = "",
    ) -> dict[str, str]:
        """
        AI 批量初翻。

        对指定的 key 列表执行 AI 翻译并存入缓存。
        返回 {key: translated_text} 映射。
        """
        results: dict[str, str] = {}
        source_translations = self._translations.get(source_lang, {})

        for key in keys:
            source_text = source_translations.get(key, "")
            if not source_text:
                continue

            translated = self.ai_engine.translate(
                text=source_text,
                source_language=source_lang,
                target_language=target_lang,
                context=context,
            )
            self.set_translation(key, target_lang, translated)

            # 记录翻译记忆
            self._record_tm(source_text, source_lang, translated, target_lang, context)
            results[key] = translated

        return results

    def ai_translate_all(
        self, source_lang: str, target_lang: str
    ) -> dict[str, str]:
        """对源语言中所有的 key 执行 AI 初翻到目标语言"""
        source_keys = list(self._translations.get(source_lang, {}).keys())
        return self.ai_translate_batch(source_keys, source_lang, target_lang)

    # ---- 翻译记忆库 ----

    def _record_tm(
        self,
        source: str,
        src_lang: str,
        target: str,
        tgt_lang: str,
        context: str,
    ) -> None:
        entry = TranslationMemoryEntry(
            source_text=source,
            source_language=src_lang,
            target_text=target,
            target_language=tgt_lang,
            context=context,
            confidence=0.7,
        )
        self._tm.append(entry)

    def search_tm(
        self,
        text: str,
        source_language: str,
        target_language: str,
        min_confidence: float = 0.6,
    ) -> list[TranslationMemoryEntry]:
        """在翻译记忆库中搜索匹配"""
        results = []
        for entry in self._tm:
            if (
                entry.source_language == source_language
                and entry.target_language == target_language
                and entry.confidence >= min_confidence
                and text.lower() in entry.source_text.lower()
            ):
                results.append(entry)
        return results

    # ---- 术语库 ----

    def add_glossary_entry(self, entry: GlossaryEntry) -> None:
        self._glossary.append(entry)

    def add_glossary_entries(self, entries: list[GlossaryEntry]) -> None:
        self._glossary.extend(entries)

    def get_glossary(self, source_lang: str, target_lang: str) -> list[GlossaryEntry]:
        return [
            e for e in self._glossary
            if e.source_language == source_lang and e.target_language == target_lang
        ]

    # ---- 资源文件导入/导出 ----

    def import_json(self, lang: str, filepath: str) -> int:
        """从 JSON 文件导入翻译"""
        if lang not in self._translations:
            raise ValueError(f"不支持的语言: {lang}")

        with open(filepath, "r", encoding="utf-8") as f:
            data: dict[str, str] = json.load(f)

        imported = 0
        for key, value in data.items():
            if isinstance(value, str):
                self._translations[lang][key] = value
                imported += 1
        return imported

    def export_json(self, lang: str, filepath: str) -> None:
        """导出翻译为 JSON 文件"""
        if lang not in self._translations:
            raise ValueError(f"不支持的语言: {lang}")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                self._translations[lang],
                f,
                ensure_ascii=False,
                indent=2,
            )

    def export_po(self, lang: str, filepath: str) -> None:
        """导出为 PO 格式（GNU gettext 兼容）"""
        if lang not in self._translations:
            raise ValueError(f"不支持的语言: {lang}")

        lang_info = LANGUAGES.get(lang, {})
        lines: list[str] = [
            f'msgid ""',
            f'msgstr ""',
            f'"Language: {lang}\\n"',
            f'"Language-Team: 海燕党 PETREL AI PARTY\\n"',
            f'"Language-Name: {lang_info.get("name_en", lang)}\\n"',
            f'"MIME-Version: 1.0\\n"',
            f'"Content-Type: text/plain; charset=UTF-8\\n"',
            f'"Content-Transfer-Encoding: 8bit\\n"',
            "",
        ]
        for key, value in self._translations[lang].items():
            lines.append(f'msgid "{key}"')
            # 多行转义
            escaped = value.replace('"', '\\"')
            lines.append(f'msgstr "{escaped}"')
            lines.append("")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def export_xliff(self, source_lang: str, target_lang: str, filepath: str) -> None:
        """导出为 XLIFF 1.2 格式"""
        source = self._translations.get(source_lang, {})
        target = self._translations.get(target_lang, {})
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        units: list[str] = []
        for key in source:
            src_text = source[key]
            tgt_text = target.get(key, "")
            units.append(f"""  <trans-unit id="{key}">
    <source>{src_text}</source>
    <target>{tgt_text}</target>
  </trans-unit>""")

        xliff_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="{source_lang}" target-language="{target_lang}" datatype="plaintext">
    <header>
      <tool tool-name="petrel-i18n" tool-version="2.0.0" />
    </header>
    <body>
{chr(10).join(units)}
    </body>
  </file>
</xliff>"""

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(xliff_content)

    # ---- 进度统计 ----

    def get_progress(self, lang: str, reference_lang: str = "zh") -> float:
        """获取指定语言的翻译完成率 (0.0 ~ 1.0)"""
        reference = self._translations.get(reference_lang, {})
        target = self._translations.get(lang, {})
        if not reference:
            return 1.0
        ref_count = len(reference)
        if ref_count == 0:
            return 1.0
        translated = sum(1 for k in reference if k in target and target[k].strip())
        return translated / ref_count

    def get_all_progress(self, reference_lang: str = "zh") -> dict[str, float]:
        """获取所有语言的翻译完成率"""
        return {
            lang: self.get_progress(lang, reference_lang)
            for lang in SUPPORTED_LANGUAGES
        }
