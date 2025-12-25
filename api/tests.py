from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from unittest.mock import patch

from .models import BanditMessages, Strategy, SignalTrigger

# Create your tests here.

class BanditMessagesViewTest(APITestCase):
    """
    Test suite for the BanditMessages API view.
    """

    def setUp(self):
        """Set up the necessary objects for the tests."""
        # We need a SignalTrigger and a Strategy for the save function to find.
        hrj_trigger = SignalTrigger.objects.create(name='hrj', description='HRJ Signals')
        Strategy.objects.create(name='HRJ Strategy', signal_trigger=hrj_trigger)

    def test_create_message_non_signal_channel_success(self):
        """
        Ensure we can create a message for a channel that does not trigger Gemini processing.
        """
        url = reverse('bandit-messages')
        data = {
            "channel_id": "12345",
            "channel_name": "general-chat",
            "message": "Hello world"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BanditMessages.objects.count(), 1)
        self.assertEqual(BanditMessages.objects.get().message, "Hello world")

    @patch('api.views.save_signal_from_gemini_response')
    @patch('api.views.generate_prompt')
    @patch('api.views.call_gemini_api')
    def test_create_message_signal_channel_gemini_returns_false(self, mock_generate_prompt, mock_call_gemini, mock_save_signal):
        """
        Test message creation when Gemini determines it's not a valid signal.
        """
        mock_call_gemini.return_value = "false"
        url = reverse('bandit-messages')
        data = {
            "channel_id": "54321",
            "channel_name": "HRJ",
            "message": "This is not a signal"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BanditMessages.objects.count(), 1)
        mock_call_gemini.assert_called_once_with(mock_generate_prompt.assert_called_once_with("HRJ", "This is not a signal"))
        mock_save_signal.assert_not_called() # Ensure we don't try to save the 'false' response

    def test_create_message_invalid_data(self):
        """
        Test that the endpoint returns a 400 error for invalid data.
        """
        url = reverse('bandit-messages')
        # Missing the 'message' field
        data = {"channel_id": "12345", "channel_name": "test-channel"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BanditMessages.objects.count(), 0)
