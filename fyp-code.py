from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
import os


@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(force=True)
    try:
        intent_name = req['queryResult']['intent']['displayName']
        
        if intent_name == 'price_lookup':
            return handle_sneaker_query(req, 'price')
        elif intent_name == 'price_lookup - custom':
            return handle_sneaker_selection(req, 'price')
        elif intent_name == 'price_lookup - custom - custom':
            return handle_final_followup(req, 'details')
        
        elif intent_name == 'sneaker_details':
            return handle_sneaker_query(req, 'details')
        elif intent_name == 'sneaker_details - custom':
            return handle_sneaker_selection(req, 'details')
        elif intent_name == 'sneaker_details - custom - custom':
            return handle_final_followup(req, 'price')
        
    except Exception as e:
        return jsonify({'fulfillmentText': f"Error: {str(e)}"})

def call_sneaker_api(brand=None, model=None, color=None):
    # Debug print to check the types of variables
    print(f"Brand: {brand}, Model: {model}, Color: {color}")
    
    # Ensure all variables are strings, not lists. Convert lists to strings if necessary.
    brand = ' '.join(brand) if isinstance(brand, list) else brand
    model = ' '.join(model) if isinstance(model, list) else model
    color = ' '.join(color) if isinstance(color, list) else color
    
    # Combine brand, model, and color into a keyword string. Include color in the search if provided.
    keywords = ' '.join(filter(None, [brand, model, color])).strip()
    
    url = "https://sneaker-database-stockx.p.rapidapi.com/getproducts"
    querystring = {"keywords": keywords, "limit": "5"}
    headers = {
        "X-RapidAPI-Key": "91d42953c0msh4fabf6143c5f317p1c50d3jsn9fe754a9da1e",
        "X-RapidAPI-Host": "sneaker-database-stockx.p.rapidapi.com"
    }
    response = requests.get(url, headers=headers, params=querystring)
    return response.json() if response.status_code == 200 else []



def handle_sneaker_query(req, info_type):
    parameters = req['queryResult']['parameters']
    brand = parameters.get('brand', None)
    model = parameters.get('model', None)
    color = parameters.get('color', None)
    
    # Convert lists to strings if necessary
    brand = ' '.join(brand) if isinstance(brand, list) else brand
    model = ' '.join(model) if isinstance(model, list) else model
    color = ' '.join(color) if isinstance(color, list) else color

    sneakers = call_sneaker_api(brand, model, color)
    
    if sneakers:
        return list_sneakers_response(sneakers, req['session'], info_type)
    else:
        return {'fulfillmentText': 'No sneakers found for the specified criteria.'}



def handle_sneaker_selection(req, info_type):
    parameters = req['queryResult']['parameters']
    selection_index = int(parameters.get('number', 1)) - 1  # Convert the index from 1-based to 0-based.
    context = next((c for c in req['queryResult']['outputContexts'] if 'sneakers' in c['parameters']), None)
    sneakers = context['parameters']['sneakers']

    if sneakers and 0 <= selection_index < len(sneakers):
        sneaker = sneakers[selection_index]
        if info_type == 'price':
            text = f"The retail price of {sneaker['shoeName']} is ${sneaker['retailPrice']} and the current lowest resell price is ${sneaker['lowestResellPrice']['stockX']}. Would you like to know more details?"
        else:  # 'details'
            # Check if the description is available, fallback to release date if not.
            if sneaker.get('description'):
                text = f"Details for {sneaker['shoeName']}: {sneaker['description']}. Would you like to know the price?"
            else:
                # Check if the release date is available as a fallback
                release_date = sneaker.get('releaseDate', 'Release date not available')
                text = f"Details are limited. Release Date: {release_date}. Would you like to know the price?"
        
        # Return the appropriate response and set the context for the selected sneaker
        return {
            'fulfillmentText': text,
            'outputContexts': [{
                'name': f"{req['session']}/contexts/selected_sneaker",
                'lifespanCount': 5,
                'parameters': {'sneaker': sneaker, 'type': info_type}
            }]
        }
    else:
        return {'fulfillmentText': 'Please select a valid number from the list.'}


def handle_final_followup(req, info_type):
    context = next((c for c in req['queryResult']['outputContexts'] if 'selected_sneaker' in c['name']), None)
    if context and 'sneaker' in context['parameters']:
        sneaker = context['parameters']['sneaker']
        if info_type == 'price':
            response_text = f"The price of {sneaker['shoeName']} is ${sneaker['retailPrice']} and the current lowest resell price is ${sneaker['lowestResellPrice']['stockX']}."
        elif info_type == 'details':
            # Check if description is available; if not, provide the release date as fallback information
            if sneaker.get('description'):
                response_text = f"Details for {sneaker['shoeName']}: {sneaker['description']}"
            else:
                release_date = sneaker.get('releaseDate', 'No release date available')
                response_text = f"Details for {sneaker['shoeName']} are currently limited. Release Date: {release_date}"
        
        return {'fulfillmentText': response_text}
    else:
        return {'fulfillmentText': 'Error: No sneaker data available.'}


def list_sneakers_response(sneakers, session, info_type):
    sneaker_list = '\n'.join([f"{idx + 1}. {sneaker['shoeName']}" for idx, sneaker in enumerate(sneakers)])
    return {
        'fulfillmentText': "Choose the correct sneaker you want:\n" + sneaker_list + "\n\nPlease refine your search if you can't see the sneaker you wanted from this list (e.g. colour or more key words) ",
        'outputContexts': [{
            'name': f"{session}/contexts/sneakers",
            'lifespanCount': 5,
            'parameters': {'sneakers': sneakers, 'type': info_type}
        }]
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

