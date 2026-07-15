"""Temporal client factory — shared by the worker and the API."""

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from ledger.config.settings import Settings


async def connect(settings: Settings) -> Client:
    return await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
