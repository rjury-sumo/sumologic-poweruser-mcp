"""
Helper functions for handling Sumo Logic async export jobs.

Sumo Logic uses an async job pattern for content exports:
1. POST to start export job → returns job_id
2. Poll GET status endpoint until status is Success/Failed
3. GET result endpoint to retrieve exported content

Based on the implementation from Hajime VSCode extension:
/Users/rjury/Documents/sumo2024/Hajime/src/api/content.ts
"""
import asyncio
from typing import Callable, Awaitable, Dict, Any

from .exceptions import APIError, TimeoutError as SumoTimeoutError


async def poll_export_job(
    job_id: str,
    content_id: str,
    get_status_func: Callable[[str, str], Awaitable[Dict[str, Any]]],
    get_result_func: Callable[[str, str], Awaitable[Dict[str, Any]]],
    max_wait_seconds: int = 300,
    poll_interval_seconds: int = 2
) -> Dict[str, Any]:
    """
    Poll async export job until completion.

    Args:
        job_id: Export job ID returned from begin export
        content_id: Content ID being exported
        get_status_func: Async function to check job status (content_id, job_id) -> response
        get_result_func: Async function to get job result (content_id, job_id) -> response
        max_wait_seconds: Maximum time to wait for job completion (default: 300s / 5min)
        poll_interval_seconds: Seconds between status polls (default: 2s)

    Returns:
        Export result dictionary with content structure

    Raises:
        SumoTimeoutError: If job doesn't complete within max_wait_seconds
        APIError: If job fails or status check fails
    """
    max_attempts = max_wait_seconds // poll_interval_seconds

    for attempt in range(max_attempts):
        # Wait before polling (don't poll immediately)
        await asyncio.sleep(poll_interval_seconds)

        try:
            # Check job status
            status_response = await get_status_func(content_id, job_id)

            # Extract status from response
            status = status_response.get('status')

            if status == 'Success':
                # Job completed successfully, get result
                result = await get_result_func(content_id, job_id)
                return result

            elif status == 'Failed':
                # Job failed
                error_msg = (
                    status_response.get('error') or
                    status_response.get('statusMessage') or
                    'Export job failed'
                )
                raise APIError(
                    f"Export job {job_id} failed: {error_msg}",
                    status_code=500
                )

            elif status == 'InProgress':
                # Continue polling
                continue

            else:
                # Unknown status
                raise APIError(
                    f"Unknown export job status: {status}",
                    status_code=500
                )

        except APIError:
            # Re-raise API errors
            raise
        except Exception as e:
            # Wrap other exceptions
            raise APIError(
                f"Error polling export job: {str(e)}",
                status_code=500
            )

    # Timeout - job didn't complete in time
    raise SumoTimeoutError(
        f"Export job {job_id} timed out after {max_wait_seconds} seconds"
    )


async def poll_folder_export_job(
    job_id: str,
    folder_type: str,
    get_status_func: Callable[[str], Awaitable[Dict[str, Any]]],
    get_result_func: Callable[[str], Awaitable[Dict[str, Any]]],
    max_wait_seconds: int = 300,
    poll_interval_seconds: int = 2
) -> Dict[str, Any]:
    """
    Poll async folder export job (Global, Admin Recommended) until completion.

    This is similar to poll_export_job but for special folder exports that
    don't require content_id in the status/result endpoints.

    Args:
        job_id: Export job ID returned from begin export
        folder_type: Type of folder (for error messages)
        get_status_func: Async function to check job status (job_id) -> response
        get_result_func: Async function to get job result (job_id) -> response
        max_wait_seconds: Maximum time to wait for job completion (default: 300s / 5min)
        poll_interval_seconds: Seconds between status polls (default: 2s)

    Returns:
        Export result dictionary with folder structure

    Raises:
        SumoTimeoutError: If job doesn't complete within max_wait_seconds
        APIError: If job fails or status check fails
    """
    max_attempts = max_wait_seconds // poll_interval_seconds

    for attempt in range(max_attempts):
        # Wait before polling
        await asyncio.sleep(poll_interval_seconds)

        try:
            # Check job status
            status_response = await get_status_func(job_id)

            # Extract status from response
            status = status_response.get('status')

            if status == 'Success':
                # Job completed successfully, get result
                result = await get_result_func(job_id)
                return result

            elif status == 'Failed':
                # Job failed
                error_msg = (
                    status_response.get('error') or
                    status_response.get('statusMessage') or
                    f'{folder_type} export job failed'
                )
                raise APIError(
                    f"{folder_type} export job {job_id} failed: {error_msg}",
                    status_code=500
                )

            elif status == 'InProgress':
                # Continue polling
                continue

            else:
                # Unknown status
                raise APIError(
                    f"Unknown {folder_type} export job status: {status}",
                    status_code=500
                )

        except APIError:
            # Re-raise API errors
            raise
        except Exception as e:
            # Wrap other exceptions
            raise APIError(
                f"Error polling {folder_type} export job: {str(e)}",
                status_code=500
            )

    # Timeout - job didn't complete in time
    raise SumoTimeoutError(
        f"{folder_type} export job {job_id} timed out after {max_wait_seconds} seconds"
    )
