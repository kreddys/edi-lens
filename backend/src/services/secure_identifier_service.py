"""
Secure Identifier Generation Service
===================================

This service provides secure, non-predictable identifier generation for
multi-tenant resources like tenant IDs, SFTP usernames, and API keys.

Security Features:
- Cryptographically secure random generation
- Non-enumerable identifiers
- Collision prevention
- Configurable identifier formats
- Audit logging for identifier generation

Usage:
    service = SecureIdentifierService()
    tenant_id = service.generate_tenant_id()
    sftp_username = service.generate_sftp_username(tenant_id, partner_name)
    api_key = service.generate_api_key()
"""

import secrets
import hashlib
import uuid
import re
import logging
from datetime import datetime
from typing import Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IdentifierType(Enum):
    """Types of identifiers that can be generated."""
    TENANT_ID = "tenant_id"
    SFTP_USERNAME = "sftp_username"
    API_KEY = "api_key"
    PARTNER_ID = "partner_id"
    SESSION_ID = "session_id"


@dataclass
class IdentifierConfig:
    """Configuration for identifier generation."""
    prefix: str
    length: int
    use_uuid: bool = False
    use_timestamp: bool = False
    include_checksum: bool = False
    allowed_chars: str = "abcdefghijklmnopqrstuvwxyz0123456789"


class SecureIdentifierService:
    """
    Service for generating secure, non-predictable identifiers.
    
    This service ensures:
    1. Cryptographically secure random generation
    2. Non-enumerable identifiers
    3. Collision prevention
    4. Consistent formatting
    5. Audit logging
    """
    
    # Identifier configurations
    CONFIGS = {
        IdentifierType.TENANT_ID: IdentifierConfig(
            prefix="tenant",
            length=16,
            use_uuid=True,
            include_checksum=True
        ),
        IdentifierType.SFTP_USERNAME: IdentifierConfig(
            prefix="sftp",
            length=12,
            use_timestamp=True
        ),
        IdentifierType.API_KEY: IdentifierConfig(
            prefix="ak",
            length=32,
            allowed_chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        ),
        IdentifierType.PARTNER_ID: IdentifierConfig(
            prefix="partner",
            length=12,
            use_uuid=True
        ),
        IdentifierType.SESSION_ID: IdentifierConfig(
            prefix="sess",
            length=24,
            allowed_chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        )
    }
    
    def __init__(self):
        """Initialize the secure identifier service."""
        self._generated_ids: Set[str] = set()
        logger.info("SecureIdentifierService initialized")
    
    def _sanitize_input(self, text: str) -> str:
        """Sanitize input text for use in identifiers."""
        if not text:
            return ""
        
        # Remove special characters and convert to lowercase
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()
        
        # Replace spaces with underscores and collapse multiple underscores
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Trim underscores from start and end
        sanitized = sanitized.strip('_')
        
        # Limit length
        return sanitized[:20]
    
    def _generate_random_string(self, length: int, allowed_chars: str) -> str:
        """Generate cryptographically secure random string."""
        return ''.join(secrets.choice(allowed_chars) for _ in range(length))
    
    def _generate_uuid_component(self) -> str:
        """Generate UUID-based component."""
        return str(uuid.uuid4()).replace('-', '')[:16]
    
    def _generate_timestamp_component(self) -> str:
        """Generate timestamp-based component."""
        # Use only last 8 digits of timestamp for shorter identifiers
        timestamp = int(datetime.utcnow().timestamp())
        return format(timestamp, 'x')[-8:]
    
    def _calculate_checksum(self, data: str) -> str:
        """Calculate checksum for identifier validation."""
        return hashlib.sha256(data.encode()).hexdigest()[:4]
    
    def _ensure_uniqueness(self, identifier: str, max_attempts: int = 10) -> str:
        """Ensure identifier uniqueness by regenerating if collision detected."""
        original_id = identifier
        attempt = 0
        
        while identifier in self._generated_ids and attempt < max_attempts:
            attempt += 1
            # Add random suffix to make unique
            suffix = self._generate_random_string(4, "0123456789abcdef")
            identifier = f"{original_id}_{suffix}"
        
        if identifier in self._generated_ids:
            raise ValueError(f"Unable to generate unique identifier after {max_attempts} attempts")
        
        self._generated_ids.add(identifier)
        return identifier
    
    def _log_generation(self, identifier_type: IdentifierType, identifier: str, context: Optional[str] = None):
        """Log identifier generation for audit purposes."""
        logger.info(
            f"Generated {identifier_type.value}: {identifier}",
            extra={
                'identifier_type': identifier_type.value,
                'identifier': identifier,
                'context': context,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
    
    def generate_tenant_id(self, organization_name: Optional[str] = None) -> str:
        """
        Generate secure tenant identifier.
        
        Args:
            organization_name: Optional organization name for context
            
        Returns:
            Secure tenant identifier (e.g., "tenant_a1b2c3d4e5f6g7h8_xy9z")
        """
        config = self.CONFIGS[IdentifierType.TENANT_ID]
        
        components = [config.prefix]
        
        # Add sanitized organization name if provided
        if organization_name:
            sanitized_org = self._sanitize_input(organization_name)
            if sanitized_org:
                components.append(sanitized_org[:8])  # Limit length
        
        # Add UUID component for uniqueness
        if config.use_uuid:
            components.append(self._generate_uuid_component()[:8])
        
        # Add random component
        random_part = self._generate_random_string(8, config.allowed_chars)
        components.append(random_part)
        
        identifier = "_".join(components)
        
        # Add checksum if configured
        if config.include_checksum:
            checksum = self._calculate_checksum(identifier)
            identifier = f"{identifier}_{checksum}"
        
        # Ensure uniqueness
        identifier = self._ensure_uniqueness(identifier)
        
        self._log_generation(IdentifierType.TENANT_ID, identifier, organization_name)
        return identifier
    
    def generate_sftp_username(self, tenant_id: str, partner_name: str) -> str:
        """
        Generate secure SFTP username.
        
        Args:
            tenant_id: Tenant identifier
            partner_name: Partner name for context
            
        Returns:
            Secure SFTP username (e.g., "sftp_a1b2c3d4_12345678")
        """
        config = self.CONFIGS[IdentifierType.SFTP_USERNAME]
        
        components = [config.prefix]
        
        # Add tenant hash (for grouping but non-enumerable)
        tenant_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:8]
        components.append(tenant_hash)
        
        # Add partner hash
        partner_hash = hashlib.sha256(partner_name.encode()).hexdigest()[:6]
        components.append(partner_hash)
        
        # Add timestamp component if configured
        if config.use_timestamp:
            timestamp_part = self._generate_timestamp_component()
            components.append(timestamp_part[-6:])  # Last 6 chars
        
        # Add random component for uniqueness
        random_part = self._generate_random_string(6, config.allowed_chars)
        components.append(random_part)
        
        identifier = "_".join(components)
        
        # Ensure uniqueness
        identifier = self._ensure_uniqueness(identifier)
        
        self._log_generation(
            IdentifierType.SFTP_USERNAME, 
            identifier, 
            f"tenant:{tenant_id}, partner:{partner_name}"
        )
        return identifier
    
    def generate_api_key(self, user_id: Optional[str] = None, scope: Optional[str] = None) -> str:
        """
        Generate secure API key.
        
        Args:
            user_id: Optional user ID for context
            scope: Optional scope/permissions for context
            
        Returns:
            Secure API key (e.g., "ak_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6")
        """
        config = self.CONFIGS[IdentifierType.API_KEY]
        
        # API keys are purely random for maximum security
        random_part = self._generate_random_string(config.length, config.allowed_chars)
        identifier = f"{config.prefix}_{random_part}"
        
        # Ensure uniqueness
        identifier = self._ensure_uniqueness(identifier)
        
        context = []
        if user_id:
            context.append(f"user:{user_id}")
        if scope:
            context.append(f"scope:{scope}")
        
        self._log_generation(
            IdentifierType.API_KEY,
            identifier,
            ", ".join(context) if context else None
        )
        return identifier
    
    def generate_partner_id(self, tenant_id: str, partner_name: str) -> str:
        """
        Generate secure partner identifier.
        
        Args:
            tenant_id: Tenant identifier
            partner_name: Partner name
            
        Returns:
            Secure partner identifier (e.g., "partner_uuid_a1b2c3d4")
        """
        config = self.CONFIGS[IdentifierType.PARTNER_ID]
        
        components = [config.prefix]
        
        # Add UUID component for uniqueness
        if config.use_uuid:
            uuid_part = self._generate_uuid_component()[:12]
            components.append(uuid_part)
        
        # Add tenant/partner hash for context but non-enumerable
        context_data = f"{tenant_id}:{partner_name}"
        context_hash = hashlib.sha256(context_data.encode()).hexdigest()[:8]
        components.append(context_hash)
        
        identifier = "_".join(components)
        
        # Ensure uniqueness
        identifier = self._ensure_uniqueness(identifier)
        
        self._log_generation(
            IdentifierType.PARTNER_ID,
            identifier,
            f"tenant:{tenant_id}, partner:{partner_name}"
        )
        return identifier
    
    def generate_session_id(self) -> str:
        """
        Generate secure session identifier.
        
        Returns:
            Secure session identifier (e.g., "sess_A1B2C3D4E5F6G7H8I9J0K1L2")
        """
        config = self.CONFIGS[IdentifierType.SESSION_ID]
        
        # Session IDs are purely random for security
        random_part = self._generate_random_string(config.length, config.allowed_chars)
        identifier = f"{config.prefix}_{random_part}"
        
        # Ensure uniqueness
        identifier = self._ensure_uniqueness(identifier)
        
        self._log_generation(IdentifierType.SESSION_ID, identifier)
        return identifier
    
    def validate_identifier_format(self, identifier: str, identifier_type: IdentifierType) -> bool:
        """
        Validate identifier format.
        
        Args:
            identifier: Identifier to validate
            identifier_type: Expected identifier type
            
        Returns:
            True if identifier format is valid
        """
        config = self.CONFIGS[identifier_type]
        
        # Check prefix
        if not identifier.startswith(f"{config.prefix}_"):
            return False
        
        # Basic length check (allowing for separators)
        if len(identifier) < len(config.prefix) + config.length:
            return False
        
        # Check allowed characters (excluding separators)
        content = identifier.replace(f"{config.prefix}_", "").replace("_", "")
        allowed_set = set(config.allowed_chars)
        
        return all(c in allowed_set for c in content)
    
    def extract_metadata(self, identifier: str, identifier_type: IdentifierType) -> dict:
        """
        Extract metadata from identifier if possible (for debugging).
        
        Args:
            identifier: Identifier to analyze
            identifier_type: Type of identifier
            
        Returns:
            Dictionary with extracted metadata
        """
        config = self.CONFIGS[identifier_type]
        metadata = {
            "type": identifier_type.value,
            "valid_format": self.validate_identifier_format(identifier, identifier_type),
            "prefix": config.prefix,
            "has_checksum": config.include_checksum
        }
        
        if config.use_timestamp and "_" in identifier:
            parts = identifier.split("_")
            if len(parts) >= 3:
                # Try to extract timestamp component (this is best-effort)
                potential_timestamp = parts[-2] if config.include_checksum else parts[-1]
                try:
                    # This is approximate since we only store last 8 hex digits
                    metadata["approximate_timestamp"] = potential_timestamp
                except ValueError:
                    pass
        
        return metadata
    
    def get_generation_stats(self) -> dict:
        """
        Get statistics about identifier generation.
        
        Returns:
            Dictionary with generation statistics
        """
        return {
            "total_generated": len(self._generated_ids),
            "types_configured": len(self.CONFIGS),
            "collision_prevention": "active"
        }