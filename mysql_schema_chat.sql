-- Script de migración para agregar funcionalidad de chat
-- Ejecutar después de crear los modelos en Python

-- Crear tabla de mensajes de chat
CREATE TABLE IF NOT EXISTS `chat_message` (
  `id` char(36) NOT NULL,
  `sender_id` char(36) NOT NULL,
  `receiver_id` char(36) NOT NULL,
  `client_request_id` char(36) NOT NULL,
  `message` varchar(500) NOT NULL,
  `status` enum('SENT','DELIVERED','READ','FAILED') NOT NULL DEFAULT 'SENT',
  `is_read` tinyint(1) NOT NULL DEFAULT 0,
  `expires_at` datetime NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_sender_id` (`sender_id`),
  KEY `idx_receiver_id` (`receiver_id`),
  KEY `idx_client_request_id` (`client_request_id`),
  KEY `idx_expires_at` (`expires_at`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_chat_message_sender` FOREIGN KEY (`sender_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_chat_message_receiver` FOREIGN KEY (`receiver_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_chat_message_client_request` FOREIGN KEY (`client_request_id`) REFERENCES `client_request` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear índices para optimizar consultas de mensajes no leídos
CREATE INDEX `idx_unread_messages` ON `chat_message` (`receiver_id`, `is_read`, `created_at`);
CREATE INDEX `idx_conversation_messages` ON `chat_message` (`client_request_id`, `created_at`);

-- Crear evento para limpiar mensajes expirados automáticamente (opcional)
-- Este evento se ejecutará diariamente a las 2:00 AM
DELIMITER $$
CREATE EVENT IF NOT EXISTS `cleanup_expired_chat_messages`
ON SCHEDULE EVERY 1 DAY
STARTS CURRENT_TIMESTAMP
DO
BEGIN
    DELETE FROM `chat_message` 
    WHERE `expires_at` < NOW();
END$$
DELIMITER ;

-- Habilitar el event scheduler si no está habilitado
SET GLOBAL event_scheduler = ON;

-- Comentarios sobre la implementación:
-- 1. Los mensajes se eliminan automáticamente después de 30 días
-- 2. Los índices optimizan las consultas de mensajes no leídos
-- 3. Las foreign keys aseguran integridad referencial
-- 4. El evento automático limpia mensajes expirados diariamente 