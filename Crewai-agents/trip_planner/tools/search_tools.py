import json
import os
import requests
from langchain.tools import tool

class SearchTools:
    @tool("Search the internet")
    def search_internet(query):
        """Useful to search the internet about a given topic and return relevant results"""
        top_result_to_return = 4
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            "X-API-KEY": os.environ["SERPER_API_KEY"],
            "content-type": "application/json",
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if "organic" not in response.json():
            return "Sorry, I couldn't find anything about that, there could be an error with your Serper API key."
        else:
            results = response.json()["organic"]
            string = []
            for result in results[:top_result_to_return]:
                try:
                    string.append(
                        "\n".join(
                            [
                                f"Title: {result['title']}",
                                f"Link: {result['link']}",
                                f"Snippet: {result['snippet']}",
                                "\n-----------------",
                            ]
                        )
                    )
                except KeyError:
                    continue
            return "\n".join(string)

    def search_flights(self, origin, destination):
        """Search for flights from origin to destination"""
        query = f"flights from {origin} to {destination}"
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            "X-API-KEY": os.environ["SERPER_API_KEY"],
            "content-type": "application/json",
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if "organic" not in response.json():
            return "Sorry, I couldn't find flight information. Please check your Serper API key."
        results = response.json()["organic"]
        string = []
        for result in results[:3]:
            try:
                string.append(
                    "\n".join(
                        [
                            f"Flight Source: {result['title']}",
                            f"Link: {result['link']}",
                            f"Description: {result['snippet']}",
                            "\n-----------------",
                        ]
                    )
                )
            except KeyError:
                continue
        return "\n".join(string) if string else "No flight information found."

    def search_cab_services(self, location):
        """Search for cab services in the specified location"""
        query = f"cab services in {location}"
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            "X-API-KEY": os.environ["SERPER_API_KEY"],
            "content-type": "application/json",
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if "organic" not in response.json():
            return "Sorry, I couldn't find cab services. Please check your Serper API key."
        results = response.json()["organic"]
        string = []
        for result in results[:3]:
            try:
                string.append(
                    "\n".join(
                        [
                            f"Cab Service: {result['title']}",
                            f"Link: {result['link']}",
                            f"Description: {result['snippet']}",
                            "\n-----------------",
                        ]
                    )
                )
            except KeyError:
                continue
        return "\n".join(string) if string else "No cab services found."

    def search_best_cafes(self, location):
        """Search for the best cafes in the specified location"""
        query = f"best cafes in {location}"
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {
            "X-API-KEY": os.environ["SERPER_API_KEY"],
            "content-type": "application/json",
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if "organic" not in response.json():
            return "Sorry, I couldn't find cafes. Please check your Serper API key."
        results = response.json()["organic"]
        string = []
        for result in results[:3]:
            try:
                string.append(
                    "\n".join(
                        [
                            f"Cafe: {result['title']}",
                            f"Link: {result['link']}",
                            f"Description: {result['snippet']}",
                            "\n-----------------",
                        ]
                    )
                )
            except KeyError:
                continue
        return "\n".join(string) if string else "No cafes found."

    def search_photos(self, location):
        """Search for photos related to the specified location"""
        query = f"{location} photos"
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": query})
        headers = {
            "X-API-KEY": os.environ["SERPER_API_KEY"],
            "content-type": "application/json",
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if "images" not in response.json():
            return "Sorry, I couldn't find photos. Please check your Serper API key."
        results = response.json()["images"]
        string = []
        for result in results[:3]:
            try:
                string.append(
                    "\n".join(
                        [
                            f"Photo Title: {result.get('title', 'No title')}",
                            f"Image URL: {result['imageUrl']}",
                            f"Source: {result.get('source', 'No source')}",
                            "\n-----------------",
                        ]
                    )
                )
            except KeyError:
                continue
        return "\n".join(string) if string else "No photos found."

    def fetch_weather(self, location):
        """Fetch current weather details for the specified location using OpenWeatherMap API"""
        api_key = os.environ.get("OPENWEATHER_API_KEY")
        if not api_key:
            return "OpenWeatherMap API key is missing."
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
        response = requests.get(url)
        if response.status_code != 200:
            return f"Could not fetch weather data for {location}. Please check the location or API key."
        data = response.json()
        try:
            weather = {
                "location": data["name"],
                "temperature": data["main"]["temp"],
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
            }
            return "\n".join(
                [
                    f"Weather in {weather['location']}:",
                    f"Temperature: {weather['temperature']}°C",
                    f"Description: {weather['description'].capitalize()}",
                    f"Humidity: {weather['humidity']}%",
                    f"Wind Speed: {weather['wind_speed']} m/s",
                    "\n-----------------",
                ]
            )
        except KeyError:
            return f"Error processing weather data for {location}."
        

        