# Módulo services: contiene la lógica de negocio de la aplicación

from .admin_log_service import (
    AdminLogService,
    log_admin_login_success,
    log_admin_login_failed,
    log_admin_logout,
    log_user_suspension,
    log_user_activation,
    log_driver_approval,
    log_withdrawal_approval,
    log_withdrawal_rejection,
    log_project_settings_update,
    log_document_verification,
    detect_suspicious_activity,
    get_high_severity_logs,
    get_critical_actions_by_admin
)
