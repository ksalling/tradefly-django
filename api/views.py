from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.renderers import JSONRenderer
from .models import BlogPost, Signal, HRJDiscordSignal, FJDiscordSignal
from .serializers import BlogPostSerializer, SignalSerializer, BanditMessageSerializer
from api.services import createBlogPost, processTradingViewSignal, DuplicateSignalError, StrategyNotFoundError, NoSubscribersError
from api.includes.gemini import generate_prompt, call_gemini_api, save_signal_from_gemini_response
import json

import logging

# Get an instance of a logger for the current module
logger = logging.getLogger(__name__)

# Create your views here.

#sunset 
class BlogPostListCreate(generics.ListCreateAPIView):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer

    def delete(self, request, *args, **kwargs):
        BlogPost.objects.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

#sunset
class BlogPostRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer
    lookup_field = 'pk'

#sunset
class BlogPostList(APIView):
    def get(self, request, format=None):
        #get title from he query parameters
        title = request.query_params.get('title', '')

        if title:
            #filter the queryset based on the title
            blog_posts = BlogPost.objects.filter(title__icontains=title)
        else:
            # if no title is provided, return all blog posts
            blog_posts = BlogPost.objects.all()

        serializer = BlogPostSerializer(blog_posts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


#sunset
class DoSomethingView(APIView):
    def get(self, request, format=None):
        logger.info("A user is accessing the DoSomethingView get method.")
        somevar = createBlogPost()
        html = '<html lang="en"><body> this is something %s.</body></html>' % request
        return Response(html, status=status.HTTP_200_OK)

    def post(self, request, format=None):
        somevar = createBlogPost()
        html = '<html lang="en"><body> this is something %s.</body></html>' % request.data
        return Response(html, status=status.HTTP_200_OK)


class ProcessTradingViewSignal(APIView):
    # By default, DRF includes the BrowsableAPIRenderer which creates the HTML page.
    # To disable it for this specific webhook endpoint, we explicitly set the
    # renderer to only handle JSON.
    renderer_classes = [JSONRenderer]
    
    # List of allowed IP addresses for TradingView webhooks
    ALLOWED_IPS = [
        '52.89.214.238',
        '34.212.75.30',
        '54.218.53.128',
        '52.32.178.7',
    ]

    def get_client_ip(self, request):
        """Helper function to get the client's real IP address, handling reverse proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def post(self, request, format=None):
        client_ip = self.get_client_ip(request)
        if client_ip not in self.ALLOWED_IPS:
            logger.warning(f"Forbidden request to ProcessTradingViewSignal from unauthorized IP: {client_ip}")
            return Response({"status": "error", "message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            logger.info(f"Received TradingView signal from authorized IP {client_ip}: {request.data}")
            processTradingViewSignal(request.data)
            return Response({"status": "success", "message": "Signal processed successfully."}, status=status.HTTP_200_OK)
        except StrategyNotFoundError as e:
            logger.warning(str(e))
            return Response({"status": "error", "message": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except DuplicateSignalError as e:
            logger.info(str(e))
            return Response({"status": "success", "message": str(e)}, status=status.HTTP_200_OK)
        except NoSubscribersError as e:
            logger.info(str(e))
            return Response({"status": "success", "message": str(e)}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"An unhandled error occurred while processing TradingView signal: {e}", exc_info=True)
            return Response({"status": "error", "message": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




#sunset
class callGeminiApi(APIView):
    def get(self, request, format=None):

        # Example 1: HRJ Signal
        hrj_message = """
        SOL/USDT (LONG)
        Leverage: 5X 
        Balance: 3% of capital
        Entry: 126.00 - (limit order)
        TP1: 146.77
        TP2: 172.55
        SL: 105.25
        R:R: 6
        """
        
        # Example 2: FJ Signal (using commas)
        fj_message = """
        **TRX/USDT (long)** 1d chart

        Entry: 0,27434 - (limit long)

        TP1: 0,2865
        TP2: 0,3029
        TP3: 0,3241
        TP4: 0,3558
        TP5: 0,3985

        SL: 0,2548

        R:R: 6,40
        <@&1354945711879491767>
        """

        # Example 3: Non-signal
        spam_message = "✅  The first target of this BTC/USDT was reached"

        print("--- Testing HRJ Signal ---")
        prompt_hrj = generate_prompt("HRJ", hrj_message)
        result_hrj = call_gemini_api(prompt_hrj)
        if result_hrj:
            print(json.dumps(result_hrj, indent=2))
            logger.info(json.dumps(result_hrj, indent=2))
        else:
            print("HRJ test failed or returned no data.")
            logger.error("HRJ test failed or returned no data.")


        print("\n--- Testing FJ Signal ---")
        prompt_fj = generate_prompt("FJ", fj_message)
        result_fj = call_gemini_api(prompt_fj)
        if result_fj:
            print(json.dumps(result_fj, indent=2))
            logger.info(json.dumps(result_fj, indent=2))
        else:
            print("FJ test failed or returned no data.")
            logger.error("FJ test failed or returned no data.")


        print("\n--- Testing Non-Signal ---")
        prompt_spam = generate_prompt("HRJ", spam_message)
        result_spam = call_gemini_api(prompt_spam)
        print(result_spam)
        logger.info(result_spam)


        return Response({"status": "success", "message": "Signal processed successfully."}, status=status.HTTP_200_OK)

class BanditMessages(APIView):
    """
    Receives and stores messages from the Bandit discord bot.
    """
    def post(self, request, format=None):
        logger.info(f"Received message from Bandit bot for channel: {request.data.get('channel_name')}")
        
        serializer = BanditMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                serializer.save()
                logger.info(f"Successfully saved message for channel ID: {serializer.data.get('channel_id')}")
                
                channel_name = request.data.get('channel_name')
                message_content = request.data.get('message')

                if channel_name in ["HRJ", "FJ"]:
                    logger.info(f"Processing message from '{channel_name}' channel with Gemini.")
                    prompt = generate_prompt(channel_name, message_content)
                    gemini_response = call_gemini_api(prompt)

                    if gemini_response and gemini_response != "false":
                        logger.info(f"Gemini returned valid signal data for '{channel_name}'. Saving to database.")
                        save_signal_from_gemini_response(gemini_response, channel_name)
                    else:
                        logger.info(f"Gemini determined the message from '{channel_name}' is not a valid signal.")

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Database error while saving Bandit message: {e}", exc_info=True)
                return Response({"error": "Failed to save message due to a database error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.warning(f"Invalid data received for Bandit message: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)