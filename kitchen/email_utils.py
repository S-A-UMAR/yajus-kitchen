"""
Email notification utilities for Yaju's Kitchen.
Sends transactional emails for order updates and confirmations.
"""
import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)


def send_order_confirmation_email(order):
    """Send order confirmation email to customer."""
    try:
        subject = f"Order Confirmation #{order.id} - Yaju's Kitchen"
        context = {
            'order': order,
            'items': order.items.all(),
            'customer_name': order.user.username if order.user else order.email.split('@')[0],
        }
        
        html_message = render_to_string('kitchen/emails/order_confirmation.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yajuskitchen.com'),
            recipient_list=[order.email],
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Order confirmation email sent for order #{order.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send order confirmation email for order #{order.id}: {e}")
        return False


def send_order_status_update_email(order, old_status):
    """Send email when order status changes."""
    try:
        # Don't send email for initial status (already sent confirmation)
        if old_status == 'received' and order.status == 'received':
            return True
            
        status_messages = {
            'preparing': 'Your order is being prepared!',
            'out_for_delivery': 'Your order is on the way!',
            'delivered': 'Your order has been delivered!',
            'cancelled': 'Your order has been cancelled',
        }
        
        if order.status not in status_messages:
            return True
            
        subject = f"Order #{order.id} Update - Yaju's Kitchen"
        context = {
            'order': order,
            'status_message': status_messages[order.status],
            'customer_name': order.user.username if order.user else order.email.split('@')[0],
        }
        
        html_message = render_to_string('kitchen/emails/order_status_update.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yajuskitchen.com'),
            recipient_list=[order.email],
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Order status update email sent for order #{order.id} - status: {order.status}")
        return True
    except Exception as e:
        logger.error(f"Failed to send order status email for order #{order.id}: {e}")
        return False


def send_payment_confirmation_email(order):
    """Send payment confirmation email."""
    try:
        if not hasattr(order, 'payment') or order.payment.status != 'success':
            return True
            
        subject = f"Payment Confirmation - Order #{order.id} - Yaju's Kitchen"
        context = {
            'order': order,
            'payment': order.payment,
            'customer_name': order.user.username if order.user else order.email.split('@')[0],
        }
        
        html_message = render_to_string('kitchen/emails/payment_confirmation.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yajuskitchen.com'),
            recipient_list=[order.email],
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Payment confirmation email sent for order #{order.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send payment confirmation for order #{order.id}: {e}")
        return False