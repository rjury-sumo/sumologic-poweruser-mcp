"""
Utility functions for converting Sumo Logic content IDs between hex and decimal formats.

Sumo Logic content IDs are stored as 16-character hexadecimal strings (e.g., "00000000005E5403")
but the web UI uses decimal format in URLs (e.g., "6181891").

Based on the implementation from Hajime VSCode extension:
/Users/rjury/Documents/sumo2024/Hajime/src/utils/contentId.ts
"""


def hex_to_decimal(hex_id: str) -> str:
    """
    Convert a hexadecimal content ID to decimal.

    Args:
        hex_id: Hexadecimal content ID (e.g., "00000000005E5403")

    Returns:
        Decimal string representation (e.g., "6181891")

    Raises:
        ValueError: If hex_id is invalid
    """
    if not hex_id or not isinstance(hex_id, str):
        raise ValueError("Invalid hex ID: must be a non-empty string")

    # Remove any whitespace
    clean_hex = hex_id.strip()

    # Remove 0x prefix if present
    if clean_hex.lower().startswith("0x"):
        clean_hex = clean_hex[2:]

    # Validate hex format
    if not all(c in "0123456789ABCDEFabcdef" for c in clean_hex):
        raise ValueError(f"Invalid hex ID format: {hex_id}")

    # Convert to decimal
    try:
        decimal = int(clean_hex, 16)
        return str(decimal)
    except ValueError as e:
        raise ValueError(f"Failed to convert hex to decimal: {hex_id}") from e


def decimal_to_hex(decimal_id: str) -> str:
    """
    Convert a decimal content ID to hexadecimal.

    Args:
        decimal_id: Decimal content ID (e.g., "6181891")

    Returns:
        Hexadecimal string representation, zero-padded to 16 characters (e.g., "00000000005E5403")

    Raises:
        ValueError: If decimal_id is invalid
    """
    if not decimal_id or not isinstance(decimal_id, str):
        raise ValueError("Invalid decimal ID: must be a non-empty string")

    # Remove any whitespace
    clean_decimal = decimal_id.strip()

    # Validate decimal format
    if not clean_decimal.isdigit():
        raise ValueError(f"Invalid decimal ID format: {decimal_id}")

    # Convert to hex
    try:
        decimal = int(clean_decimal)
        hex_val = hex(decimal)[2:].upper()  # Remove '0x' prefix and uppercase

        # Pad to 16 characters (standard Sumo Logic ID length)
        return hex_val.zfill(16)
    except ValueError as e:
        raise ValueError(f"Failed to convert decimal to hex: {decimal_id}") from e


def format_content_id(hex_id: str) -> str:
    """
    Format a content ID showing both hex and decimal representations.

    Args:
        hex_id: Hexadecimal content ID

    Returns:
        Formatted string (e.g., "00000000005E5403 (6181891)")
    """
    try:
        decimal = hex_to_decimal(hex_id)
        return f"{hex_id} ({decimal})"
    except ValueError:
        return hex_id  # Return original if conversion fails


def is_valid_hex_id(hex_id: str) -> bool:
    """
    Validate if a string is a valid Sumo Logic hex content ID.

    Args:
        hex_id: String to validate

    Returns:
        True if valid hex ID format (16 hex characters)
    """
    if not hex_id or not isinstance(hex_id, str):
        return False

    clean_hex = hex_id.strip()

    # Sumo Logic IDs are typically 16 characters hex
    if len(clean_hex) != 16:
        return False

    return all(c in "0123456789ABCDEFabcdef" for c in clean_hex)


def is_valid_decimal_id(decimal_id: str) -> bool:
    """
    Validate if a string is a valid decimal content ID.

    Args:
        decimal_id: String to validate

    Returns:
        True if valid decimal ID format
    """
    if not decimal_id or not isinstance(decimal_id, str):
        return False

    clean_decimal = decimal_id.strip()
    return clean_decimal.isdigit() and len(clean_decimal) > 0


def normalize_to_hex(id_str: str) -> str:
    """
    Normalize a content ID to hex format, accepting either hex or decimal input.

    Args:
        id_str: Content ID in either hex or decimal format

    Returns:
        Hexadecimal content ID (16 characters, uppercase)

    Raises:
        ValueError: If ID is invalid or format cannot be determined
    """
    if not id_str or not isinstance(id_str, str):
        raise ValueError("Invalid ID: must be a non-empty string")

    clean_id = id_str.strip()

    # Check if it's already valid hex
    if is_valid_hex_id(clean_id):
        return clean_id.upper()

    # Try to parse as hex with 0x prefix
    if clean_id.lower().startswith("0x"):
        hex_part = clean_id[2:]
        if all(c in "0123456789ABCDEFabcdef" for c in hex_part):
            return hex_part.upper().zfill(16)

    # Try as decimal
    if is_valid_decimal_id(clean_id):
        return decimal_to_hex(clean_id)

    raise ValueError(f"Cannot normalize ID - invalid format: {id_str}")
