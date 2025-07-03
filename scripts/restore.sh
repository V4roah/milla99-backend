#!/bin/bash

# ============================================================================
# SCRIPT DE RESTAURACIÓN PARA MILLA99 MYSQL
# ============================================================================

# Configuración
DB_CONTAINER="milla99-mysql"
DB_NAME="milla99_db"
DB_USER="milla99_user"
DB_PASSWORD="milla99_password"
BACKUP_DIR="/backups"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 Script de Restauración para Milla99 MySQL${NC}"

# Verificar que el contenedor esté corriendo
if ! docker ps | grep -q $DB_CONTAINER; then
    echo -e "${RED}❌ Error: Contenedor $DB_CONTAINER no está corriendo${NC}"
    exit 1
fi

# Función para mostrar backups disponibles
show_backups() {
    echo -e "${BLUE}📋 Backups disponibles:${NC}"
    if [ -d "$BACKUP_DIR" ]; then
        ls -la $BACKUP_DIR/milla99_backup_*.sql.gz 2>/dev/null | while read line; do
            echo -e "${YELLOW}  $line${NC}"
        done
    else
        echo -e "${RED}❌ Directorio de backups no encontrado${NC}"
    fi
}

# Función para restaurar backup específico
restore_backup() {
    local backup_file=$1
    
    echo -e "${YELLOW}⚠️ ADVERTENCIA: Esta operación sobrescribirá la base de datos actual${NC}"
    echo -e "${YELLOW}📁 Backup a restaurar: $backup_file${NC}"
    
    read -p "¿Estás seguro de que quieres continuar? (y/N): " confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}🔄 Iniciando restauración...${NC}"
        
        # Crear backup de seguridad antes de restaurar
        echo -e "${YELLOW}💾 Creando backup de seguridad antes de restaurar...${NC}"
        ./scripts/backup.sh
        
        # Restaurar backup
        echo -e "${YELLOW}📦 Restaurando backup...${NC}"
        gunzip -c $backup_file | docker exec -i $DB_CONTAINER mysql \
            -u$DB_USER \
            -p$DB_PASSWORD \
            $DB_NAME
            
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Restauración completada exitosamente!${NC}"
        else
            echo -e "${RED}❌ Error durante la restauración${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}❌ Restauración cancelada${NC}"
        exit 0
    fi
}

# Función para restaurar backup más reciente
restore_latest() {
    local latest_backup=$(ls -t $BACKUP_DIR/milla99_backup_*.sql.gz 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        echo -e "${RED}❌ No se encontraron backups${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}📁 Backup más reciente: $latest_backup${NC}"
    restore_backup "$latest_backup"
}

# Menú principal
echo -e "${BLUE}Selecciona una opción:${NC}"
echo -e "${YELLOW}1) Ver backups disponibles${NC}"
echo -e "${YELLOW}2) Restaurar backup más reciente${NC}"
echo -e "${YELLOW}3) Restaurar backup específico${NC}"
echo -e "${YELLOW}4) Salir${NC}"

read -p "Opción: " choice

case $choice in
    1)
        show_backups
        ;;
    2)
        restore_latest
        ;;
    3)
        show_backups
        echo ""
        read -p "Ingresa el nombre completo del archivo de backup: " backup_file
        if [ -f "$BACKUP_DIR/$backup_file" ]; then
            restore_backup "$BACKUP_DIR/$backup_file"
        else
            echo -e "${RED}❌ Archivo no encontrado${NC}"
            exit 1
        fi
        ;;
    4)
        echo -e "${GREEN}👋 ¡Hasta luego!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Opción inválida${NC}"
        exit 1
        ;;
esac 