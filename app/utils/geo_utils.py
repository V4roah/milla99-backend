from geoalchemy2.shape import to_shape
import requests
from typing import Optional
from app.core.config import settings


def wkb_to_coords(wkb):
    """
    Convierte un campo WKBElement a un diccionario con latitud y longitud.
    Args:
        wkb: WKBElement de la base de datos
    Returns:
        dict con 'lat' y 'lng' o None si wkb es None
    """
    if wkb is None:
        return None
    point = to_shape(wkb)
    return {"lat": point.y, "lng": point.x}


def get_address_from_coords(lat: float, lng: float) -> Optional[str]:
    """
    Obtiene una dirección legible a partir de coordenadas de latitud y longitud
    utilizando la API de Geocodificación Inversa de Google.
    """
    if not lat or not lng:
        return None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": settings.GOOGLE_API_KEY,
        "language": "es"  # Para obtener resultados en español
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            return data["results"][0].get("formatted_address")
        else:
            print(
                f"Error de Geocoding API: {data.get('status')}, {data.get('error_message')}")
            return "Dirección no encontrada"

    except requests.exceptions.RequestException as e:
        print(f"Error de red al consultar Google Geocoding API: {e}")
        return "Error al obtener dirección"
    except Exception as e:
        print(f"Error inesperado en get_address_from_coords: {e}")
        return "Error al procesar dirección"


def get_time_and_distance_from_google(origin_lat, origin_lng, destination_lat, destination_lng):
    """
    Llama a la API de Google Distance Matrix para obtener tiempo y distancia entre dos puntos.
    Retorna una tupla (distancia_en_metros, duracion_en_segundos) o (None, None) si falla.
    """
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lng}",
        "destinations": f"{destination_lat},{destination_lng}",
        "units": "metric",
        "key": settings.GOOGLE_API_KEY
    }

    print(f"🔍 DEBUG GOOGLE API: Consultando Distance Matrix")
    print(f"🔍 DEBUG GOOGLE API: Origen: {origin_lat}, {origin_lng}")
    print(f"🔍 DEBUG GOOGLE API: Destino: {destination_lat}, {destination_lng}")
    print(f"🔍 DEBUG GOOGLE API: URL: {url}")
    print(
        f"🔍 DEBUG GOOGLE API: API Key configurada: {'Sí' if settings.GOOGLE_API_KEY else 'No'}")

    try:
        response = requests.get(url, params=params)
        print(f"🔍 DEBUG GOOGLE API: Status Code: {response.status_code}")

        response.raise_for_status()
        data = response.json()
        print(f"🔍 DEBUG GOOGLE API: Respuesta: {data}")

        if data.get("status") == "OK" and data["rows"][0]["elements"][0]["status"] == "OK":
            distance = data["rows"][0]["elements"][0]["distance"]["value"]
            duration = data["rows"][0]["elements"][0]["duration"]["value"]
            print(
                f"✅ DEBUG GOOGLE API: Distancia: {distance}m, Duración: {duration}s")
            return distance, duration
        else:
            print(
                f"❌ DEBUG GOOGLE API: Error en respuesta - Status: {data.get('status')}")
            print(
                f"❌ DEBUG GOOGLE API: Error message: {data.get('error_message', 'No disponible')}")
            if data.get("rows") and data["rows"][0].get("elements"):
                element_status = data["rows"][0]["elements"][0].get("status")
                print(f"❌ DEBUG GOOGLE API: Element status: {element_status}")
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"❌ DEBUG GOOGLE API: Error de red: {e}")
        return None, None
    except Exception as e:
        print(f"❌ DEBUG GOOGLE API: Error inesperado: {e}")
        return None, None
