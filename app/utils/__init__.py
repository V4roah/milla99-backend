# Módulo utils: utilidades y funciones auxiliares reutilizables

# Importaciones lazy para evitar circular imports
def get_admin_log_decorators():
    """Retorna los decoradores de admin log de forma lazy"""
    from .admin_log_decorators import (
        log_withdrawal_approval,
        log_withdrawal_rejection,
        log_balance_adjustment,
        log_project_settings_update,
        log_admin_password_change,
        log_driver_force_approval,
        log_document_verification,
        log_user_suspension,
        log_user_activation,
        log_critical_action,
        log_with_details
    )
    return {
        'log_withdrawal_approval': log_withdrawal_approval,
        'log_withdrawal_rejection': log_withdrawal_rejection,
        'log_balance_adjustment': log_balance_adjustment,
        'log_project_settings_update': log_project_settings_update,
        'log_admin_password_change': log_admin_password_change,
        'log_driver_force_approval': log_driver_force_approval,
        'log_document_verification': log_document_verification,
        'log_user_suspension': log_user_suspension,
        'log_user_activation': log_user_activation,
        'log_critical_action': log_critical_action,
        'log_with_details': log_with_details
    }

# Para mantener compatibilidad, podemos exponer las funciones directamente
# pero solo cuando se necesiten


def __getattr__(name):
    """Permite acceso lazy a los decoradores"""
    decorators = get_admin_log_decorators()
    if name in decorators:
        return decorators[name]
    raise AttributeError(f"module 'app.utils' has no attribute '{name}'")
