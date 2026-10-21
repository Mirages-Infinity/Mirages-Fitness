"""Estimacion de calorias y macros de una foto de comida, via OpenAI Vision."""
import base64
import json

from openai import OpenAI

PROMPT = (
    'Sos un nutricionista. Mira la foto de comida y estima, para la porcion '
    'visible: un nombre breve del plato en español, calorias totales, '
    'proteina en gramos, carbohidratos en gramos y grasa en gramos. '
    'Si no es comida o no se distingue, usa name="Comida" y valores en 0. '
    'Respondé SOLO un JSON con las claves exactas: '
    '{"name": str, "calories": int, "protein": number, "carbs": number, "fat": number}'
)


def analyze_food_photo(image_bytes, api_key):
    """Devuelve {'name', 'calories', 'protein', 'carbs', 'fat'} o None si falla."""
    try:
        client = OpenAI(api_key=api_key)
        b64 = base64.b64encode(image_bytes).decode('ascii')
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': PROMPT},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}},
                ],
            }],
            max_tokens=200,
            response_format={'type': 'json_object'},
        )
        data = json.loads(response.choices[0].message.content)
        return {
            'name': str(data.get('name') or 'Comida')[:150],
            'calories': max(0, int(float(data.get('calories') or 0))),
            'protein': max(0, float(data.get('protein') or 0)),
            'carbs': max(0, float(data.get('carbs') or 0)),
            'fat': max(0, float(data.get('fat') or 0)),
        }
    except Exception:
        # Red caida, clave invalida, respuesta inesperada: se cae a carga manual.
        return None
