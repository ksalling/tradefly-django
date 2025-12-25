from django.contrib import admin

from .models import (
    BlogPost,
    SupportedExchange,
    Strategy,
    UserProfile,
    UserApi,
    Signal,
    StrategySubscription,
    UserTrade,
    HRJDiscordSignal,
    FJDiscordSignal,
    HRJTakeProfitTrade,
    FJTakeProfitTrade,
    BanditMessages,
    SignalTrigger,
)

# Change the default Django admin site headers and titles
admin.site.site_header = "TradeFly Administration"
admin.site.site_title = "TradeFly Admin Portal"
admin.site.index_title = "Welcome to the TradeFly Admin Portal"


class HRJTakeProfitTradesInline(admin.TabularInline):
    model = HRJTakeProfitTrade
    extra = 1


@admin.register(HRJDiscordSignal)
class HRJDiscordSignalsAdmin(admin.ModelAdmin):
    list_display = ('id', 'strategy', 'asset', 'trade_type', 'leverage', 'balance', 'entry_price', 'entry_order_type', 'stop_loss')
    list_filter = ('trade_type', 'asset')
    inlines = [HRJTakeProfitTradesInline]


class FJTakeProfitTradesInline(admin.TabularInline):
    model = FJTakeProfitTrade
    extra = 1


@admin.register(FJDiscordSignal)
class FJDiscordSignalsAdmin(admin.ModelAdmin):
    list_display = ('id', 'strategy', 'asset', 'trade_type', 'entry_price', 'entry_order_type', 'stop_loss')
    list_filter = ('trade_type', 'asset')
    inlines = [FJTakeProfitTradesInline]


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'content', 'published_date')

@admin.register(SupportedExchange)
class SupportedExchangeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(SignalTrigger)
class SignalTriggerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)

@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ('strategy_id', 'name', 'description', 'signal_trigger', 'created_at', 'updated_at')
    list_filter = ('name',)
    search_fields = ('name', 'description')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'auth_user', 'firstname', 'lastname', 'country', 'created_at')
    search_fields = ('firstname', 'lastname', 'auth_user__username')

@admin.register(UserApi)
class UserApiAdmin(admin.ModelAdmin):
    list_display = ('id', 'auth_user', 'exchange')
    list_filter = ('exchange',)
    search_fields = ('auth_user__username',)

@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ('id', 'strategy', 'symbol', 'side', 'price', 'orderType', 'tradeSide', 'created_at')
    list_filter = ('strategy', 'symbol', 'side', 'tradeSide')
    search_fields = ('symbol',)

@admin.register(StrategySubscription)
class StrategySubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'auth_user', 'strategy', 'user_api', 'portfolio_percentage', 'status', 'leverage_amount', 'max_tp_trades', 'enable_sl_trail', 'enable_sms_confirm')
    list_filter = ('status', 'strategy')
    search_fields = ('auth_user__username',)

@admin.register(UserTrade)
class UserTradeAdmin(admin.ModelAdmin):
    list_display = ('id', 'auth_user', 'signal', 'position_id', 'exchange_mark_price', 'trade_value', 'trade_qty')
    search_fields = ('auth_user__username',)

@admin.register(BanditMessages)
class BanditMessagesAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel_name', 'channel_id', 'message', 'created_at')
    list_filter = ('channel_name',)
    search_fields = ('channel_name', 'message')