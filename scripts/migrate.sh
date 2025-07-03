#!/bin/bash

# ============================================================================
# SCRIPT DE MIGRACIÓN PARA MILLA99 MYSQL
# ============================================================================

# Configuración
DB_CONTAINER="milla99-mysql"
DB_NAME="milla99_db"
DB_USER="milla99_user"
DB_PASSWORD="milla99_password"
SOURCE_DB_HOST="localhost"
SOURCE_DB_USER="root"
SOURCE_DB_PASSWORD="root"
SOURCE_DB_NAME="milla99"
MIGRATION_FILE="migration_$(date +%Y%m%d_%H%M%S).sql"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 Script de Migración para Milla99 MySQL${NC}"
echo -e "${BLUE}Migrando datos de MySQL local a Docker${NC}"

# Verificar que el contenedor esté corriendo
if ! docker ps | grep -q $DB_CONTAINER; then
    echo -e "${RED}❌ Error: Contenedor $DB_CONTAINER no está corriendo${NC}"
    echo -e "${YELLOW}💡 Ejecuta: docker-compose up -d${NC}"
    exit 1
fi

# Verificar conexión a MySQL local
echo -e "${YELLOW}🔍 Verificando conexión a MySQL local...${NC}"
if ! mysql -h$SOURCE_DB_HOST -u$SOURCE_DB_USER -p$SOURCE_DB_PASSWORD -e "USE $SOURCE_DB_NAME;" 2>/dev/null; then
    echo -e "${RED}❌ Error: No se puede conectar a MySQL local${NC}"
    echo -e "${YELLOW}💡 Verifica que MySQL esté corriendo y las credenciales sean correctas${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Conexión a MySQL local exitosa${NC}"

# Verificar conexión a MySQL Docker
echo -e "${YELLOW}🔍 Verificando conexión a MySQL Docker...${NC}"
if ! docker exec $DB_CONTAINER mysql -u$DB_USER -p$DB_PASSWORD -e "USE $DB_NAME;" 2>/dev/null; then
    echo -e "${RED}❌ Error: No se puede conectar a MySQL Docker${NC}"
    echo -e "${YELLOW}💡 Verifica que el contenedor esté corriendo${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Conexión a MySQL Docker exitosa${NC}"

# Crear backup de MySQL local antes de migrar
echo -e "${YELLOW}💾 Creando backup de MySQL local...${NC}"
mysqldump -h$SOURCE_DB_HOST -u$SOURCE_DB_USER -p$SOURCE_DB_PASSWORD \
    --single-transaction \
    --routines \
    --triggers \
    $SOURCE_DB_NAME > "backup_local_$(date +%Y%m%d_%H%M%S).sql"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backup de MySQL local creado${NC}"
else
    echo -e "${RED}❌ Error al crear backup de MySQL local${NC}"
    exit 1
fi

# Crear backup de MySQL Docker antes de migrar
echo -e "${YELLOW}💾 Creando backup de MySQL Docker...${NC}"
docker exec $DB_CONTAINER mysqldump -u$DB_USER -p$DB_PASSWORD \
    --single-transaction \
    --routines \
    --triggers \
    $DB_NAME > "backup_docker_$(date +%Y%m%d_%H%M%S).sql"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backup de MySQL Docker creado${NC}"
else
    echo -e "${YELLOW}⚠️ No se pudo crear backup de Docker (probablemente está vacío)${NC}"
fi

# Exportar datos de MySQL local
echo -e "${YELLOW}📦 Exportando datos de MySQL local...${NC}"
mysqldump -h$SOURCE_DB_HOST -u$SOURCE_DB_USER -p$SOURCE_DB_PASSWORD \
    --single-transaction \
    --routines \
    --triggers \
    --no-create-db \
    --add-drop-table \
    $SOURCE_DB_NAME > $MIGRATION_FILE

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Datos exportados exitosamente${NC}"
    echo -e "${GREEN}📁 Archivo de migración: $MIGRATION_FILE${NC}"
else
    echo -e "${RED}❌ Error al exportar datos${NC}"
    exit 1
fi

# Importar datos a MySQL Docker
echo -e "${YELLOW}📥 Importando datos a MySQL Docker...${NC}"
docker exec -i $DB_CONTAINER mysql -u$DB_USER -p$DB_PASSWORD $DB_NAME < $MIGRATION_FILE

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Datos importados exitosamente${NC}"
else
    echo -e "${RED}❌ Error al importar datos${NC}"
    exit 1
fi

# Verificar migración
echo -e "${YELLOW}🔍 Verificando migración...${NC}"

# Contar tablas en origen
SOURCE_TABLES=$(mysql -h$SOURCE_DB_HOST -u$SOURCE_DB_USER -p$SOURCE_DB_PASSWORD -e "SHOW TABLES FROM $SOURCE_DB_NAME;" | wc -l)
SOURCE_TABLES=$((SOURCE_TABLES - 1)) # Restar la línea del header

# Contar tablas en destino
DEST_TABLES=$(docker exec $DB_CONTAINER mysql -u$DB_USER -p$DB_PASSWORD -e "SHOW TABLES FROM $DB_NAME;" | wc -l)
DEST_TABLES=$((DEST_TABLES - 1)) # Restar la línea del header

echo -e "${BLUE}📊 Tablas en origen: $SOURCE_TABLES${NC}"
echo -e "${BLUE}📊 Tablas en destino: $DEST_TABLES${NC}"

if [ $SOURCE_TABLES -eq $DEST_TABLES ]; then
    echo -e "${GREEN}✅ Migración verificada exitosamente${NC}"
else
    echo -e "${YELLOW}⚠️ Advertencia: Número de tablas no coincide${NC}"
fi

# Limpiar archivo temporal
rm $MIGRATION_FILE
echo -e "${GREEN}🧹 Archivo temporal eliminado${NC}"

echo -e "${GREEN}🎉 Migración completada exitosamente!${NC}"
echo -e "${BLUE}📋 Resumen:${NC}"
echo -e "${BLUE}  - Backup local creado${NC}"
echo -e "${BLUE}  - Backup Docker creado${NC}"
echo -e "${BLUE}  - Datos migrados exitosamente${NC}"
echo -e "${BLUE}  - Verificación completada${NC}"
echo -e "${YELLOW}💡 Ahora puedes usar: docker-compose up -d${NC}" 