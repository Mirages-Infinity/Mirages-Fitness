"""Estimacion de calorias y macros de una foto de comida, via OpenAI Vision."""
import base64
import json

from openai import OpenAI

PROMPT = (
    'Sos un nutricionista. Mira la foto de comida y estima, para la porcion '
    'visible: un nombre breve del plato en español, una lista breve de los '
    'ingredientes que identificás separados por coma, calorias totales, '
    'proteina en gramos, carbohidratos en gramos y grasa en gramos. '
    'Si hay algo que no podés determinar con certeza con solo mirar la foto '
    '(aceite o manteca agregada, azucar, un ingrediente tapado u oculto, el '
    'tipo exacto de carne o salsa, etc.), marcá "complete" en false y escribi '
    'en "question" UNA sola pregunta corta en español pidiendole ese dato '
    'puntual al usuario para completar el calculo. Si estas razonablemente '
    'seguro de haber identificado todo lo relevante, marcá "complete" en '
    'true y "question" en null. '
    'Si no es comida o no se distingue nada, usa name="Comida", items="", '
    'complete=true, question=null y valores en 0. '
    'Respondé SOLO un JSON con las claves exactas: '
    '{"name": str, "items": str, "calories": int, "protein": number, '
    '"carbs": number, "fat": number, "complete": bool, "question": str|null}'
)


def analyze_food_photo(image_bytes, api_key, extra_context=None):
    """Devuelve {'name','items','calories','protein','carbs','fat','complete','question'}
    o None si falla. extra_context: aclaracion del usuario (segunda pasada) sobre
    algo que la IA no pudo determinar con la foto sola."""
    try:
        client = OpenAI(api_key=api_key)
        b64 = base64.b64encode(image_bytes).decode('ascii')
        prompt = PROMPT
        if extra_context:
            prompt += (
                f' El usuario aclaró lo siguiente sobre el plato: "{extra_context}". '
                'Usá ese dato para ajustar el calculo y marcá "complete" en true.'
            )
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}},
                ],
            }],
            max_tokens=300,
            response_format={'type': 'json_object'},
        )
        data = json.loads(response.choices[0].message.content)
        question = data.get('question')
        return {
            'name': str(data.get('name') or 'Comida')[:150],
            'items': str(data.get('items') or '')[:300],
            'calories': max(0, int(float(data.get('calories') or 0))),
            'protein': max(0, float(data.get('protein') or 0)),
            'carbs': max(0, float(data.get('carbs') or 0)),
            'fat': max(0, float(data.get('fat') or 0)),
            'complete': bool(data.get('complete', True)),
            'question': str(question)[:200] if question else None,
        }
    except Exception:
        # Red caida, clave invalida, respuesta inesperada: se cae a carga manual.
        return None
