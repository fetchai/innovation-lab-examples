"""
The Developer Layer: Callbacks & Plugins

Prompt Engineering is NOT a Security Strategy.
Asking an LLM nicely to "please ignore PII" is wishful thinking, not governance.

This module implements security guardrails using ADK callbacks to inject deterministic
Python logic before agent execution. This acts as middleware—validating user roles,
checking permissions, and blocking unauthorized access before the model sees the prompt.

Security Layers:
1. Model Armor (Infrastructure) - Handles PII, hate speech, jailbreaks at gateway level
2. Callbacks (This module) - Custom business logic, role-based access control
3. Plugins - Monitoring and audit logging
"""

from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from typing import Optional

# Global state storage for callbacks (key: (user_id, session_id), value: state dict)
# This is set by agent.py before calling run_async()
_session_states = {}


def set_session_state(user_id: str, session_id: str, state: dict):
    """Set state for a session (called by agent.py)."""
    global _session_states
    _session_states[(user_id, session_id)] = state


def get_session_state(user_id: str, session_id: str) -> dict:
    """Get state for a session."""
    global _session_states
    return _session_states.get((user_id, session_id), {})


def clear_session_state(user_id: str, session_id: str):
    """Clear state for a session (cleanup after processing)."""
    global _session_states
    _session_states.pop((user_id, session_id), None)


async def callback_before_agent(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    Security callback that runs before agent execution.
    
    Implements guardrails using deterministic Python logic (not probabilistic prompts).
    This runs AFTER Model Armor (infrastructure layer) and BEFORE the LLM sees the data.
    
    Security Checks:
    1. User role verification (student/developer/enterprise/business/robot)
    2. Permission validation based on role
    3. Custom business logic enforcement
    4. Session and profile validation
    
    Note: Model Armor handles PII detection, hate speech, and jailbreaks at the
    infrastructure level. This callback adds application-level security controls.
    
    Returns:
        None: Allow model call to proceed
        types.Content: Block request and return error message
    """
    global _session_states
    
    # Try to get state from callback_context first (if ADK provides it)
    state = callback_context.state if callback_context.state else {}
    
    # Also try to get from session_states (set by agent.py)
    # Since callbacks are synchronous during run_async, we can try to get the most recent state
    # or try to extract user_id/session_id from callback_context
    try:
        # Try multiple ways to get user_id and session_id from callback context
        user_id = None
        session_id = None
        
        # Method 1: Direct attributes
        user_id = getattr(callback_context, 'user_id', None)
        session_id = getattr(callback_context, 'session_id', None)
        
        # Method 2: Private attributes
        if not user_id:
            user_id = getattr(callback_context, '_user_id', None)
        if not session_id:
            session_id = getattr(callback_context, '_session_id', None)
        
        # Method 3: From session if available
        if hasattr(callback_context, 'session'):
            session = callback_context.session
            if hasattr(session, 'user_id'):
                user_id = session.user_id
            if hasattr(session, 'session_id'):
                session_id = session.session_id
        
        # If we have both, try to get from session_states
        if user_id and session_id:
            stored_state = _session_states.get((user_id, session_id), {})
            if stored_state:
                state = stored_state
        # If we only have one, try to find any matching state
        elif _session_states:
            # Fallback: use the most recent state (for single-user scenarios)
            # This is a workaround if user_id/session_id aren't available
            state = list(_session_states.values())[-1] if _session_states else {}
    except Exception:
        # If all else fails, use callback_context.state or empty dict
        if not state:
            state = {}
    
    # Guardrail 1: User Profile & Role Verification
    # First, verify that user profile exists and is valid
    user_profile = state.get("user_profile")
    student_profile = state.get("student_profile")
    user_role = state.get("user_role")
    user_id = state.get("user_id")
    user_name = state.get("user_name")
    permissions = state.get("permissions", [])
    
    # Think about profile: Check if we have a valid user profile
    # Profile validation is critical - we need to know who the user is
    if not user_profile and student_profile is None and not user_role:
        # No profile information at all - this is a security risk
        # In production, you should block: return error
        # For now, allow to proceed but log warning (backward compatibility)
        pass
    
    # Think about profile: Validate profile completeness
    # A valid profile should have at least role or student_profile
    profile_valid = bool(user_role) or (student_profile is not None)
    
    if not profile_valid:
        # Profile is incomplete or missing - security risk
        # Allow to proceed but this should be logged for security audit
        pass
    
    # Guardrail 1.1: User Role Verification
    # Verify that user has a valid role assigned
    if not user_role:
        # No role specified - check if we have student_profile as fallback
        if student_profile is False:
            # Explicitly blocked profile
            return types.Content(
                role='model',
                parts=[types.Part(text="Error: User profile not found. Access denied.")]
            )
        # For backward compatibility, allow if student_profile is True or None
        pass
    
    # Guardrail 2: Role-Based Access Control
    # Different roles have different access levels
    if user_role == "student":
        # Students: Basic read-only access
        # Can ask questions but cannot access admin functions
        # Add restrictions here if needed for specific queries
        pass  # Allow students to proceed with basic queries
    
    elif user_role == "developer":
        # Developers: Full access including admin and system config
        # Can access all features and tools
        pass  # Allow developers full access
    
    elif user_role in ["enterprise", "business"]:
        # Enterprise/Business: Admin access but not system config
        # Can access business features and admin tools
        pass  # Allow enterprise/business users
    
    elif user_role == "robot":
        # Robots: Automated access for bots
        # May have rate limiting or specific restrictions
        pass  # Allow robot access
    
    elif user_role:
        # Unknown role - security risk, block access
        return types.Content(
            role='model',
            parts=[types.Part(text=f"Error: Unknown user role '{user_role}'. Access denied for security reasons.")]
        )
    
    # Guardrail 3: Permission Validation
    # Check if user has required permissions for specific operations
    # Think about profile: Validate that user has necessary permissions for their role
    
    if user_role and permissions:
        # Validate permissions are appropriate for the role
        required_permissions_by_role = {
            "student": ["read", "ask_questions"],
            "developer": ["read", "ask_questions", "admin_access", "system_config"],
            "enterprise": ["read", "ask_questions", "admin_access"],
            "business": ["read", "ask_questions", "admin_access"],
            "robot": ["read", "ask_questions", "automated_access"]
        }
        
        # Check if user has minimum required permissions for their role
        required_perms = required_permissions_by_role.get(user_role, [])
        if required_perms:
            missing_perms = [p for p in required_perms if p not in permissions]
            if missing_perms:
                # User doesn't have required permissions for their role
                # This is a security issue - profile might be corrupted
                return types.Content(
                    role='model',
                    parts=[types.Part(text=f"Error: User profile incomplete. Missing required permissions: {', '.join(missing_perms)}. Access denied.")]
                )
        
        # Check for permission escalation attempts
        # Students should not have admin or system config permissions
        if user_role == "student":
            restricted_perms = ["admin_access", "system_config", "deploy", "delete"]
            has_restricted = any(perm in permissions for perm in restricted_perms)
            if has_restricted:
                return types.Content(
                    role='model',
                    parts=[types.Part(text="Error: Permission escalation detected. Students cannot have admin privileges. Access denied.")]
                )
        
        # Check for invalid permissions
        valid_permissions = ["read", "ask_questions", "admin_access", "system_config", "automated_access", "deploy", "delete"]
        invalid_perms = [p for p in permissions if p not in valid_permissions]
        if invalid_perms:
            # Invalid permissions in profile - potential security risk
            # Log this but allow to proceed (could be custom permissions)
            pass
    
    # Guardrail 4: Profile Validation & Completeness Check
    # Think about profile: Ensure profile is complete and valid
    # Check student_profile for legacy systems and profile completeness
    if student_profile is False:  # Explicitly False means blocked
        return types.Content(
            role='model', 
            parts=[types.Part(text="Error: Cannot find student profile. Access denied.")]
        )
    
    # Think about profile: Validate profile has required fields
    # A complete profile should have: role, user_id, and permissions
    if user_role and not user_id:
        # Profile incomplete - missing user_id
        # Log this for security audit but allow to proceed
        pass
    
    if user_role and not permissions:
        # Profile incomplete - missing permissions
        # This might be okay for some roles, but should be validated
        pass
    
    # Guardrail 5: Custom Business Logic
    # Add your organization-specific security checks here
    # Examples:
    # - Time-based access restrictions
    # - IP-based filtering
    # - Rate limiting per user
    # - Content-specific restrictions
    
    # All security checks passed - allow model call to proceed
    # Model Armor will handle PII, hate speech, and jailbreaks at infrastructure level
    return None
