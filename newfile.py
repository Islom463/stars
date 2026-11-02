"""
Telegram Stars, Gif va SMM Nakrutka boti - Groq (Llama 3.1) AI versiya
Barcha kalitlar Render Environment'dan o'qiladi:
BOT_TOKEN, GROQ_API_KEY, SMM_API_KEY
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.request
import time
import aiohttp
import asyncio
import logging
import re
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

