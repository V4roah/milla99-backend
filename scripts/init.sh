#!/bin/bash

# ============================================================================
# SCRIPT DE INICIALIZACIÓN PARA MILLA99 BACKEND EN DOCKER
# ============================================================================

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Crear carpetas necesarias
BACKUP_DIR="./backups"
LOGS_DIR="./logs"
STATIC_DIR="./static"

mkdir -p $BACKUP_DIR $LOGS_DIR $STATIC_DIR

echo -e "${GREEN}✅ Carpetas necesarias creadas (backups, logs, static)${NC}"

# Levantar servicios de Docker
if [ -f "docker-compose.yml" ]; then
    echo -e "${YELLOW}🚀 Levantando servicios con docker-compose...${NC}"
    docker-compose up -d
else
    echo -e "${RED}❌ No se encontró docker-compose.yml en el directorio actual${NC}"
    exit 1
fi

# Verificar estado de los contenedores
sleep 3
echo -e "${BLUE}🔍 Estado de los contenedores:${NC}"
docker-compose ps

# Mostrar accesos útiles
echo -e "\n${GREEN}🎯 Accesos rápidos:${NC}"
echo -e "${YELLOW}API Docs:     http://localhost:8000/docs${NC}"
echo -e "${YELLOW}phpMyAdmin:   http://localhost:8080${NC}"
echo -e "${YELLOW}Backups:      $BACKUP_DIR${NC}"
echo -e "${YELLOW}Logs:         $LOGS_DIR${NC}"
echo -e "${YELLOW}Static:       $STATIC_DIR${NC}"

echo -e "\n${GREEN}✅ Inicialización completada. ¡Listo para trabajar!${NC}" 