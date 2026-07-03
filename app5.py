from flask import Flask, render_template, jsonify, request
import psycopg2
import base64
import requests
from datetime import datetime
from geopy.geocoders import Nominatim  # For geocoding

app = Flask(__name__)

# OpenWeather API Key
API_KEY = '' #app key

# Function to connect to the database
def get_db_connection():
    conn = psycopg2.connect(
        user= "", #username
        password= "", #pass
        host="",
        dbname="",
        port="" #port no.
    )
    return conn

# Function to get latitude and longitude using city name
def get_lat_lon(city_name):
    geolocator = Nominatim(user_agent="city_guide_app")
    location = geolocator.geocode(city_name)
    if location:
        return location.latitude, location.longitude
    return None, None

# Route for the home page
@app.route("/")
def home():
    return render_template("start.html")

# Route for the top page
@app.route("/top")
def top():
    return render_template("top.html")

# Route for the travel page
@app.route("/travel")
def travel():
    print("inside travel")
    city_code = request.args.get("city_code", "")  # Default to empty string if not found
    return render_template("travel.html", city_code=city_code)

# Route for the hotel page
@app.route("/hotel")
def hotel():
    print("inside hotel")
    city_code = request.args.get("city_code", "")  # Use "city_code" instead of "city_city"
    city_name = request.args.get("city_name", "")  # Get the city name from the query parameters
    print(f"City Code: {city_code}")  # Debugging statement
    print(f"City Name: {city_name}")  # Debugging statement
    return render_template("hotel.html", city_code=city_code, city_name=city_name)

# Route for the weather page
@app.route("/weather")
def weather():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    print("inside weather")

    # Fetch all cities from the database
    cursor.execute("SELECT city FROM city;")
    cities = cursor.fetchall()

    print("data loaded")
    # Close the database connection
    cursor.close()
    conn.close()

    print("before html update")

    # Pass the cities to the template
    return render_template("indexW.html", cities=cities)

# Route for the explore page (exp_world.html)
@app.route("/explore")
def explore():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    print("inside explore")

    # Fetch all countries from the database
    cursor.execute("SELECT id, country, image FROM country;")
    countries = cursor.fetchall()

    # Convert binary image data to base64 for rendering in HTML
    country_data = []
    for country in countries:
        country_id, country_name, image_binary = country
        if image_binary:
            image_base64 = base64.b64encode(image_binary).decode('utf-8')
        else:
            image_base64 = None
        country_data.append({
            "id": country_id,
            "name": country_name,
            "image": image_base64
        })

    # Close the database connection
    cursor.close()
    conn.close()

    # Pass the country data to the template
    return render_template("exp_world.html", countries=country_data)

# Route for country details (cont.html)
@app.route("/country/<int:country_id>")
def country_details(country_id):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    print("inside country")

    # Fetch all unique cities for the selected country by joining tables
    cursor.execute("""
        SELECT DISTINCT city.id, city.city, city.image 
        FROM city
        JOIN relation ON city.id = relation.city_id
        WHERE relation.country_id = %s;
    """, (country_id,))
    cities = cursor.fetchall()

    # Convert binary image data to base64 for rendering in HTML
    city_data = []
    for city in cities:
        city_id, city_name, image_binary = city
        if image_binary:
            image_base64 = base64.b64encode(image_binary).decode('utf-8')
        else:
            image_base64 = None
        city_data.append({
            "id": city_id,
            "name": city_name,
            "image": image_base64
        })

    # Close the database connection
    cursor.close()
    conn.close()

    # Render the country details page with city data
    return render_template("cont.html", cities=city_data)

# Route for city details (des.html)
@app.route("/des/<int:city_id>")
def city_details(city_id):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    print("inside destination")

    # Fetch all cities for the dropdown
    cursor.execute("SELECT city FROM city;")
    cities = cursor.fetchall()

    # Fetch city details from the database
    cursor.execute("""
        SELECT city, description, image, code
        FROM city
        WHERE id = %s;
    """, (city_id,))
    city = cursor.fetchone()

    # Convert binary image data to base64 for rendering in HTML
    city_data = None
    if city:
        city_name, city_description, image_binary, city_code = city
        image_base64 = base64.b64encode(image_binary).decode('utf-8') if image_binary else None

        # Get latitude and longitude using the city name
        latitude, longitude = get_lat_lon(city_name)

        city_data = {
            "name": city_name,
            "description": city_description,
            "image": image_base64,
            "code": city_code,
            "latitude": latitude,
            "longitude": longitude
        }

    # Fetch restaurants using the relation table
    cursor.execute("""
        SELECT r.id, r.restaurant, r.image, r.description, r.avg_price, r.ink
        FROM restaurant r
        JOIN relation rel ON r.id = rel.restaurant_id
        WHERE rel.city_id = %s;
    """, (city_id,))
    restaurants = cursor.fetchall()

    # Convert restaurant image data to base64
    restaurant_data = []
    for restaurant in restaurants:
        restaurant_id, restaurant_name, image_binary, description, avg_price, ink = restaurant
        image_base64 = base64.b64encode(image_binary).decode('utf-8') if image_binary else None
        restaurant_data.append({
            "id": restaurant_id,
            "name": restaurant_name,
            "image": image_base64,
            "description": description,
            "avg_price": avg_price,
            "link": ink
        })

    # Close database connection
    cursor.close()
    conn.close()

    # Render city details with restaurants and cities for the dropdown
    return render_template("des.html", city=city_data, restaurants=restaurant_data, cities=cities)

# Function to fetch weather data
def fetch_weather(city_name):
    print("fetch weather")
    try:
        url = f'http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={API_KEY}&units=metric'
        response = requests.get(url)
        if response.status_code != 200:
            return None

        data = response.json()

        # Extract timezone offset (in seconds)
        timezone_offset = data['city']['timezone']

        # Extract current weather and next 2 days' forecast
        current_weather = data['list'][0]
        tomorrow_weather = data['list'][8]
        day_after_tomorrow_weather = data['list'][16]

        # Format the data
        weather_data = {
            'timezone_offset': timezone_offset,  # Timezone offset in seconds
            'today': {
                'temperature': current_weather['main']['temp'],
                'description': current_weather['weather'][0]['description'],
                'humidity': current_weather['main']['humidity']
            },
            'tomorrow': {
                'temperature': tomorrow_weather['main']['temp'],
                'description': tomorrow_weather['weather'][0]['description'],
                'humidity': tomorrow_weather['main']['humidity']
            },
            'day_after_tomorrow': {
                'temperature': day_after_tomorrow_weather['main']['temp'],
                'description': day_after_tomorrow_weather['weather'][0]['description'],
                'humidity': day_after_tomorrow_weather['main']['humidity']
            }
        }

        return weather_data
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None

# Route for the map page
@app.route("/map")
def map_page():
    print("Map route accessed")  # Debugging statement
    return render_template("indexM.html")

# Route to handle weather data requests
@app.route('/get_weather', methods=['POST'])
def get_weather():
    city = request.json.get('city')
    if not city:
        return jsonify({'error': 'No city selected'}), 400

    weather_data = fetch_weather(city)
    if not weather_data:
        return jsonify({'error': 'Failed to fetch weather data'}), 500

    return jsonify(weather_data)

# Route to fetch city image
@app.route('/get_city_image', methods=['POST'])
def get_city_image():
    city = request.json.get('city')
    if not city:
        return jsonify({'error': 'No city selected'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch the city image from the database
    cursor.execute("SELECT image FROM city WHERE city = %s;", (city,))
    city_data = cursor.fetchone()

    cursor.close()
    conn.close()

    if city_data and city_data[0]:
        image_base64 = base64.b64encode(city_data[0]).decode('utf-8')
        return jsonify({'image': image_base64})
    else:
        return jsonify({'error': 'Image not found'}), 404

if __name__ == "__main__":
    app.run(debug=True)