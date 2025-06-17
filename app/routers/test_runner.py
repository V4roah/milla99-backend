from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
import subprocess
import json
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
from pathlib import Path
from app.core.dependencies.admin_auth import get_current_admin


router = APIRouter(
    prefix="/tests",
    tags=["ADMIN - tests"],
    dependencies=[Depends(get_current_admin)]
)


class TestResult:
    def __init__(self):
        self.results = []
        self.summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0
        }
        self.start_time = None
        self.end_time = None

    def add_result(self, test_name: str, status: str, duration: float, error_message: str = None):
        self.results.append({
            "test_name": test_name,
            "status": status,
            "duration": duration,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        })

    def update_summary(self, status: str):
        self.summary[status] += 1
        self.summary["total"] += 1

    def set_duration(self, duration: float):
        self.summary["duration"] = duration


def run_tests_with_json_output() -> Dict:
    """Ejecuta los tests y devuelve los resultados en formato JSON"""
    test_result = TestResult()

    # Crear archivo temporal para el reporte JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json_report_path = temp_file.name

    try:
        # Ejecutar pytest con reporte JSON
        cmd = [
            "pytest",
            "app/test/",
            "--json-report",
            f"--json-report-file={json_report_path}",
            "--json-report-indent=2",
            "-v"
        ]

        # Ejecutar el comando
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd()
        )

        stdout, stderr = process.communicate()

        # Leer el reporte JSON
        if os.path.exists(json_report_path):
            with open(json_report_path, 'r') as f:
                json_data = json.load(f)

            # Procesar los resultados
            if 'tests' in json_data:
                for test in json_data['tests']:
                    status = test.get('outcome', 'unknown')
                    duration = test.get('duration', 0)
                    test_name = test.get('nodeid', 'unknown')
                    error_message = None

                    if status == 'failed':
                        error_message = test.get(
                            'call', {}).get('longrepr', '')

                    test_result.add_result(
                        test_name, status, duration, error_message)
                    test_result.update_summary(status)

            # Actualizar duración total
            if 'summary' in json_data:
                test_result.set_duration(
                    json_data['summary'].get('duration', 0))

        return {
            "success": process.returncode == 0,
            "summary": test_result.summary,
            "results": test_result.results,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": process.returncode
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": test_result.summary,
            "results": test_result.results
        }
    finally:
        # Limpiar archivo temporal
        if os.path.exists(json_report_path):
            os.unlink(json_report_path)


def run_tests_with_html_output() -> str:
    """Ejecuta los tests y genera un reporte HTML"""
    # Crear directorio para reportes si no existe
    reports_dir = Path("static/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Generar nombre único para el reporte
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_report_path = reports_dir / f"test_report_{timestamp}.html"

    try:
        # Ejecutar pytest con reporte HTML
        cmd = [
            "pytest",
            "app/test/",
            f"--html={html_report_path}",
            "--self-contained-html",
            "-v"
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd()
        )

        stdout, stderr = process.communicate()

        # Cambiado: solo verifica que el archivo exista
        if html_report_path.exists():
            return str(html_report_path)
        else:
            raise Exception(f"Error generando reporte HTML: {stderr}")

    except Exception as e:
        raise Exception(f"Error ejecutando tests: {str(e)}")


@router.post("/run", description="""
Ejecuta todos los tests del proyecto y devuelve los resultados en formato JSON.

**Permisos:** Solo administradores pueden ejecutar tests.

**Respuesta:**
- `success`: Boolean indicando si todos los tests pasaron
- `summary`: Resumen de resultados (total, passed, failed, skipped, errors, duration)
- `results`: Lista detallada de cada test con su estado y duración
- `stdout`: Salida estándar de pytest
- `stderr`: Salida de errores de pytest
""")
async def run_tests():
    """Ejecuta todos los tests y devuelve resultados en JSON - Solo ADMIN"""
    try:
        results = run_tests_with_json_output()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=results
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando tests: {str(e)}"
        )


@router.post("/run-html", description="""
Ejecuta todos los tests del proyecto y genera un reporte HTML visual.

**Permisos:** Solo administradores pueden ejecutar tests.

**Respuesta:**
- URL del reporte HTML generado que se puede abrir en el navegador
""")
async def run_tests_html():
    """Ejecuta todos los tests y genera un reporte HTML - Solo ADMIN"""
    try:
        html_report_path = run_tests_with_html_output()

        # Devolver la URL del reporte
        report_url = f"/static/reports/{Path(html_report_path).name}"

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "Reporte HTML generado exitosamente",
                "report_url": report_url,
                "file_path": html_report_path
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando reporte HTML: {str(e)}"
        )


@router.get("/reports", description="""
Obtiene la lista de reportes HTML disponibles.

**Permisos:** Solo administradores pueden ver reportes.
""")
async def list_reports():
    """Lista todos los reportes HTML disponibles - Solo ADMIN"""
    reports_dir = Path("static/reports")

    if not reports_dir.exists():
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"reports": [], "total": 0}
        )

    reports = []
    for report_file in reports_dir.glob("test_report_*.html"):
        reports.append({
            "name": report_file.name,
            "url": f"/static/reports/{report_file.name}",
            "size": report_file.stat().st_size,
            "created": datetime.fromtimestamp(report_file.stat().st_mtime).isoformat()
        })

    # Ordenar por fecha de creación (más reciente primero)
    reports.sort(key=lambda x: x["created"], reverse=True)

    return {
        "reports": reports,
        "total": len(reports)
    }


@router.post("/run-specific", description="""
Ejecuta tests específicos basados en patrones o nombres de archivo.

**Permisos:** Solo administradores pueden ejecutar tests.

**Parámetros:**
- `test_pattern`: Patrón para filtrar tests (ej: "test_auth", "test_client_request")
""")
async def run_specific_tests(test_pattern: str):
    """Ejecuta tests específicos basados en un patrón - Solo ADMIN"""
    try:
        # Crear archivo temporal para el reporte JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json_report_path = temp_file.name

        cmd = [
            "pytest",
            f"app/test/{test_pattern}",
            "--json-report",
            f"--json-report-file={json_report_path}",
            "--json-report-indent=2",
            "-v"
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd()
        )

        stdout, stderr = process.communicate()

        # Leer el reporte JSON
        results = {"success": process.returncode ==
                   0, "stdout": stdout, "stderr": stderr}

        if os.path.exists(json_report_path):
            with open(json_report_path, 'r') as f:
                json_data = json.load(f)
            results.update(json_data)

        # Limpiar archivo temporal
        if os.path.exists(json_report_path):
            os.unlink(json_report_path)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=results
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando tests específicos: {str(e)}"
        )
