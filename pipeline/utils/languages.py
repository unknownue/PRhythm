#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Language utilities for PRhythm.
"""

# Map of language codes to language names
LANGUAGE_MAP = {
    "en": "English",
    "zh-cn": "Chinese",
    "zh-tw": "Traditional Chinese",
    "jp": "Japanese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ru": "Russian",
    "ko": "Korean",
    "ar": "Arabic",
    "pt": "Portuguese"
}

# List of supported languages
SUPPORTED_LANGUAGES = list(LANGUAGE_MAP.keys())


def get_language_name(language_code: str) -> str:
    """
    Get language name from language code
    
    Args:
        language_code: Language code
        
    Returns:
        str: Language name
    """
    return LANGUAGE_MAP.get(language_code, "Unknown")


def is_supported_language(language_code: str) -> bool:
    """
    Check if a language is supported
    
    Args:
        language_code: Language code
        
    Returns:
        bool: True if language is supported, False otherwise
    """
    return language_code in SUPPORTED_LANGUAGES
