from rest_framework import serializers
from .models import (
    SupportedExchange,
    Strategy,
    UserProfile,
    UserApi,
    Signal,
    StrategySubscription,
    UserTrade,
    BlogPost,
    BanditMessages,
)

class BlogPostSerializer(serializers.ModelSerializer):
    class Meta:        
        model = BlogPost
        fields = ['id', 'title', 'content', 'published_date']

class SupportedExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportedExchange
        fields = '__all__'


class StrategySerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = '__all__'


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class UserApiSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserApi
        fields = '__all__'


class SignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signal
        fields = '__all__'


class StrategySubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategySubscription
        fields = ['id', 'auth_user', 'strategy', 'user_api', 'portfolio_percentage', 'status', 'leverage_amount', 'max_tp_trades', 'enable_sl_trail', 'enable_sms_confirm', 'created_at', 'updated_at']


class UserTradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTrade
        fields = '__all__'

class BanditMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BanditMessages
        fields = ['id', 'channel_id', 'channel_name', 'message', 'created_at']