#!/bin/bash

# ============================================================================
# SCRIPT DE BACKUP AUTOMÁTICO PARA MILLA99 MYSQL
# ============================================================================

# Configuración
DB_CONTAINER="milla99-mysql"
DB_NAME="milla99_db"
DB_USER="milla99_user"
DB_PASSWORD="milla99_password"
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="milla99_backup_${DATE}.sql"
COMPRESSED_FILE="milla99_backup_${DATE}.sql.gz"
RETENTION_DAYS=30

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 Iniciando backup de Milla99 MySQL...${NC}"

# Verificar que el contenedor esté corriendo
if ! docker ps | grep -q $DB_CONTAINER; then
    echo -e "${RED}❌ Error: Contenedor $DB_CONTAINER no está corriendo${NC}"
    exit 1
fi

# Crear backup
echo -e "${YELLOW}📦 Creando backup: $BACKUP_FILE${NC}"
docker exec $DB_CONTAINER mysqldump \
    -u$DB_USER \
    -p$DB_PASSWORD \
    --single-transaction \
    --routines \
    --triggers \
    $DB_NAME > $BACKUP_FILE

# Verificar si el backup fue exitoso
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backup creado exitosamente${NC}"
    
    # Comprimir backup
    echo -e "${YELLOW}🗜️ Comprimiendo backup...${NC}"
    gzip $BACKUP_FILE
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Backup comprimido: $COMPRESSED_FILE${NC}"
        
        # Mover al directorio de backups
        mv $COMPRESSED_FILE $BACKUP_DIR/
        echo -e "${GREEN}✅ Backup movido a: $BACKUP_DIR/$COMPRESSED_FILE${NC}"
        
        # Limpiar backups antiguos
        echo -e "${YELLOW}🧹 Limpiando backups antiguos (más de $RETENTION_DAYS días)...${NC}"
        find $BACKUP_DIR -name "milla99_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
        
        echo -e "${GREEN}🎉 Backup completado exitosamente!${NC}"
        echo -e "${GREEN}📁 Ubicación: $BACKUP_DIR/$COMPRESSED_FILE${NC}"
        
        # Mostrar tamaño del backup
        BACKUP_SIZE=$(du -h $BACKUP_DIR/$COMPRESSED_FILE | cut -f1)
        echo -e "${GREEN}📊 Tamaño: $BACKUP_SIZE${NC}"
        
    else
        echo -e "${RED}❌ Error al comprimir backup${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Error al crear backup${NC}"
    exit 1
fi 