# TODO
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

import click
import uvicorn
from faker import Faker
from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel, ConfigDict, Field

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.tortoise import Filter

logger = logging.getLogger("uvicorn")
