from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
#from fernet_fields import EncryptedCharField
from django.utils import timezone
from django.contrib.auth import get_user_model
#from django_crypto_fields.fields import EncryptedTextField

auth_user = get_user_model()


# Create your models here.
class BlogPost(models.Model):
    title = models.CharField(max_length=150)
    content = models.TextField()
    published_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class SupportedExchange(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        db_table = 'supported_exchanges'
        verbose_name_plural = "Supported Exchanges"

    def __str__(self):
        return self.name


class SignalTrigger(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="The unique name for the trigger (e.g., 'hrj', 'fj', 'tradingview').")
    description = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.description or self.name

    class Meta:
        db_table = 'signal_triggers'
        verbose_name = "Signal Trigger"
        verbose_name_plural = "Signal Triggers"

class Strategy(models.Model):
    strategy_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    signal_trigger = models.ForeignKey(SignalTrigger, on_delete=models.SET_NULL, null=True, blank=True, help_text="Link to the source that triggers this strategy's signals.")
    password = models.CharField(max_length=50, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'strategies'
        verbose_name_plural = "Strategies"

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user_id = models.AutoField(primary_key=True)
    auth_user = models.ForeignKey(auth_user, on_delete=models.CASCADE, db_column='auth_user_id', blank=True, null=True)
    
    # Profile fields
    firstname = models.CharField(max_length=255, blank=True, null=True)
    lastname = models.CharField(max_length=255, blank=True, null=True)
    street1 = models.CharField(max_length=255, blank=True, null=True)
    street2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    zip = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
    
    def __str__(self):
        if self.auth_user:
            return self.auth_user.username
        return f"Profile {self.user_id}"


class UserApi(models.Model):
    auth_user = models.ForeignKey(auth_user, on_delete=models.CASCADE, db_column='auth_user_id', blank=True, null=True)
    exchange = models.ForeignKey(SupportedExchange, on_delete=models.CASCADE, db_column='exchange_id', blank=True, null=True)
    #api_key = EncryptedTextField(max_length=255, null=True)
    #api_secret = EncryptedTextField(max_length=255, null=True)
    api_key = models.CharField(max_length=255, null=True)
    api_secret = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = 'user_api'
        verbose_name = "User API Credential"

    def __str__(self):
        if self.auth_user and self.exchange:
            return f"{self.auth_user.username} - {self.exchange.name}"
        return f"UserApi {self.id}"


class Signal(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id', blank=True, null=True)
    symbol = models.CharField(max_length=255)
    side = models.CharField(max_length=255)
    
    # Note: Using CharField because SQL definition is varchar(40). 
    # If you perform math on these, consider changing to DecimalField in the future.
    price = models.CharField(max_length=40, blank=True, null=True)
    orderType = models.CharField(max_length=255, blank=True, null=True)
    
    tpPrice = models.CharField(max_length=40, blank=True, null=True)
    tpStopType = models.CharField(max_length=255, blank=True, null=True)
    tpOrderType = models.CharField(max_length=255, blank=True, null=True)
    tpOrderPrice = models.CharField(max_length=40, blank=True, null=True)
    
    slPrice = models.CharField(max_length=40, blank=True, null=True)
    slStopType = models.CharField(max_length=255, blank=True, null=True)
    slOrderType = models.CharField(max_length=255, blank=True, null=True)
    
    tradeSide = models.CharField(max_length=20, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'signal'
        verbose_name = "TradingView Signal"

    def __str__(self):
        return f"{self.symbol} {self.side} ({self.id})"


class StrategySubscription(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Disabled', 'Disabled'),
    ]

    auth_user = models.ForeignKey(auth_user, on_delete=models.CASCADE, db_column='auth_user_id')
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id')
    user_api = models.ForeignKey(UserApi, on_delete=models.SET_NULL, db_column='user_api_id', blank=True, null=True)
    
    # Enforcing the CHECK constraint (0-100)
    portfolio_percentage = models.IntegerField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='Active',
        blank=True, 
        null=True
    )
    
    leverage_amount = models.IntegerField(blank=True, null=True)
    max_tp_trades = models.IntegerField(blank=True, null=True)
    enable_sl_trail = models.BooleanField(default=True)
    enable_sms_confirm = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'strategy_subscriptions'
        verbose_name = "User Strategy Subscription"


    def __str__(self):
        if self.auth_user and self.strategy:
            return f"{self.auth_user.username} -> {self.strategy.name}"
        return f"Subscription {self.id}"


class UserTrade(models.Model):
    auth_user = models.ForeignKey(auth_user, on_delete=models.RESTRICT, db_column='auth_user_id')
    signal = models.ForeignKey(Signal, on_delete=models.CASCADE, db_column='signal_id')
    
    position_id = models.CharField(max_length=20, blank=True, null=True)
    exchange_mark_price = models.CharField(max_length=20, blank=True, null=True)
    trade_value = models.CharField(max_length=20, blank=True, null=True)
    trade_qty = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = 'user_trades'

    def __str__(self):
        if self.auth_user:
            return f"Trade {self.id} for {self.auth_user.username}"
        return f"Trade {self.id}"

class HRJDiscordSignal(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id', blank=True, null=True)
    asset = models.CharField(max_length=255)
    trade_type = models.CharField(max_length=5, choices=[('long', 'Long'), ('short', 'Short')])
    leverage = models.IntegerField(default=1)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    entry_price = models.DecimalField(max_digits=20, decimal_places=10)
    entry_order_type = models.CharField(max_length=6, choices=[('market', 'Market'), ('limit', 'Limit')])
    stop_loss = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        db_table = 'hrj_discord_signal'
        verbose_name = "HRJ Discord Signal"
    
    def __str__(self):
        return f"{self.asset} {self.trade_type}"

class FJDiscordSignal(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id', blank=True, null=True)
    asset = models.CharField(max_length=255)
    trade_type = models.CharField(max_length=5, choices=[('long', 'Long'), ('short', 'Short')])
    entry_price = models.DecimalField(max_digits=20, decimal_places=10)
    entry_order_type = models.CharField(max_length=6, choices=[('market', 'Market'), ('limit', 'Limit')])
    stop_loss = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        db_table = 'fj_discord_signal'
        verbose_name = "FJ Discord Signal"
    
    def __str__(self):
        return f"{self.asset} {self.trade_type}"
    
class SIGSCANDiscordSignal(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, db_column='strategy_id', blank=True, null=True)
    asset = models.CharField(max_length=255)
    trade_type = models.CharField(max_length=5, choices=[('long', 'Long'), ('short', 'Short')])
    entry_price = models.DecimalField(max_digits=20, decimal_places=10)
    entry_order_type = models.CharField(max_length=6, choices=[('market', 'Market'), ('limit', 'Limit')])
    stop_loss = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        db_table = 'sigscan_discord_signal'
        verbose_name = "SIGSCAN Discord Signal"
    
    def __str__(self):
        return f"{self.asset} {self.trade_type}"
    
class HRJTakeProfitTrade(models.Model):
    signal = models.ForeignKey(HRJDiscordSignal, on_delete=models.CASCADE, db_column='signal_id')
    series_num = models.IntegerField(default=1)
    tp_price = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        db_table = 'hrj_take_profit_trade'
        verbose_name = "HRJ Take Profit Trade"
        unique_together = ('signal', 'series_num')
    
    def __str__(self):
        return f"TP {self.series_num} for HRJ Signal {self.signal_id}"

class FJTakeProfitTrade(models.Model):
    signal = models.ForeignKey(FJDiscordSignal, on_delete=models.CASCADE, db_column='signal_id')
    series_num = models.IntegerField()
    tp_price = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        db_table = 'fj_take_profit_trade'
        verbose_name = "FJ Take Profit Trade"
        unique_together = ('signal', 'series_num')
    
    def __str__(self):
        return f"TP {self.series_num} for FJ Signal {self.signal_id}"

class SIGSCANTakeProfitTrade(models.Model):
    signal = models.ForeignKey(SIGSCANDiscordSignal, on_delete=models.CASCADE, db_column='signal_id')
    series_num = models.IntegerField()
    tp_price = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        db_table = 'sigscan_take_profit_trade'
        verbose_name = "SIGSCAN Take Profit Trade"
        unique_together = ('signal', 'series_num')
    
    def __str__(self):
        return f"TP {self.series_num} for SIGSCAN Signal {self.signal_id}"

class BanditMessages(models.Model):
    channel_id = models.CharField(max_length=255, blank=True, null=True)
    channel_name = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'banditmessages'
        verbose_name_plural = "Bandit Messages"

    def __str__(self):
        return f"Message from {self.channel_name} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"