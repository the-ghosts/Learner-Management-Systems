
from django.shortcuts import render, redirect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

from api import serializer as api_serializer
from api import models as api_models
from userauths.models import User, Profile

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny 
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response

import random
from decimal import Decimal
import stripe

import requests

stripe.api_key= settings.STRIPE_SECRET_KEY

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = api_serializer.MyTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = api_serializer.RegisterSerilizer

def generate_random_otp(length= 7):
    otp = ''.join([str(random.randint(0, 9)) for _ in range(length)])
    return otp

class ResetPasswordEmailVerifyApiView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.UserSerializer

    def get_object(self):
        email = self.kwargs['email'] #api/v1/password-email-reset-verify/michael@gmail.com

        user = User.objects.filter(email=email).first()

        if user:
            uuidb64 = user.pk
            refresh = RefreshToken.for_user(user)
            refresh_token = str(refresh.access_token)

            user.refresh_token = refresh_token
            user.otp = generate_random_otp()
            user.save()

            link = f"http://localhost:5173/create-new-password/?otp={user.otp}&uuidb64={uuidb64}&refresh_token={refresh_token}"

            context = {
                "link": link,
                "username": user.username,
            }
            subject = "Password Reset Link - LMS"
            text_body= render_to_string("email/reset_password.txt", context)
            html_body= render_to_string("email/reset_password.html", context)

            msg= EmailMultiAlternatives(
                subject= subject,
                from_email= settings.FROM_EMAIL,
                to= [user.email],
                body= text_body,    
                )
            msg.attach_alternative(html_body, "text/html")
            msg.send()

            print ("Password reset link:", link)
        
        return user

class PasswordChangeAPIView(generics.CreateAPIView):
    persmission_classes = [AllowAny]
    serializer_class = api_serializer.UserSerializer

    def create(self, request, *args, **kwargs):
        otp= request.data['otp']
        uuidb64= request.data['uuidb64']
        password= request.data['password']

        user = User.objects.get(id=uuidb64, otp=otp)
        if user:
            user.set_password(password)
            user.otp = ""
            user.save()

            return Response({"message": "Password Changed Successfully"}, status=status.HTTP_201_CREATED)
        else:
            return Response({"message": "User Not Found"}, status=status.HTTP_404_NOT_FOUND)


class CategoryListAPIView(generics.ListAPIView):
    queryset= api_models.Category.objects.filter(active=True)
    serializer_class= api_serializer.CategorySerializer
    permission_classes=[AllowAny]

class CourseListAPIView(generics.ListAPIView):
    queryset= api_models.Course.objects.filter(platform_status="Published", teacher_course_status= "Published")
    serializer_class= api_serializer.CourseSerializer
    permission_classes= [AllowAny]

class CourseDetailListAPIView(generics.RetrieveAPIView):
    serializer_class= api_serializer.CourseSerializer
    permission_classes=[AllowAny]
    queryset= api_models.Course.objects.filter(platform_status="Published", teacher_course_status= "Published")

    def get_object(self):
        slug= self.kwargs['slug']
        course= api_models.Course.objects.get(slug=slug, platform_status="Published", teacher_course_status= "Published")
        return course

class CartAPIView(generics.CreateAPIView):
    queryset= api_models.Cart.objects.all()
    serializer_class= api_serializer.CartSerializer
    permission_classes= [AllowAny]

    def create(self, request, *args, **kwargs):
        course_id=request.data['course_id']
        user_id= request.data['user_id']
        price= request.data['price']
        country_name= request.data['country_name']
        cart_id= request.data['cart_id']

        course= api_models.Course.objects.filter(id=course_id).first()

        if user_id !="undefined":
            user= User.objects.filter(id=user_id).first()
        else:
            user=None
        
        try:
            country_object= api_models.Country.objects.filter(name= country_name).first()
            country= country_object.name
        except:
            country_object= None
            country= "United Kingdom"
        
        if country_object:
            tax_rate= country_object.tax_rate/100
        else:
            tax_rate= 0
        
        cart= api_models.Cart.objects.filter(cart_id= cart_id, course=course).first()

        if cart:
            cart.course= course
            cart.user= user
            cart.price= price
            cart.tax_fee= Decimal(price) * Decimal(tax_rate)
            cart.country= country
            cart.cart_id= cart_id
            cart.total= Decimal(cart.price) + Decimal(cart.tax_fee)
            cart.save()
            
            return Response({"message": "Cart Updated Successfully"}, status= status.HTTP_200_OK)
        else:
            cart= api_models.Cart()

            cart.course= course
            cart.user= user
            cart.price= price
            cart.tax_fee= Decimal(price) * Decimal(tax_rate)
            cart.country= country
            cart.cart_id= cart_id
            cart.total= Decimal(cart.price) + Decimal(cart.tax_fee)
            cart.save()

            return Response({"message": "Cart Created Successfully"}, status= status.HTTP_201_CREATED)

class CartListAPIView(generics.ListAPIView):
    serializer_class = api_serializer.CartSerializer
    permission_classes= [AllowAny]

    def get_queryset(self):
        cart_id = self.kwargs['cart_id']
        queryset= api_models.Cart.objects.filter(cart_id=cart_id)
        return queryset

class CartItemDeleteAPIView(generics.DestroyAPIView):
    serializer_class= api_serializer.CartSerializer
    permission_classes= [AllowAny]

    def get_object(self):
        cart_id = self.kwargs['cart_id']
        item_id = self.kwargs['item_id']
        return api_models.Cart.objects.filter(cart_id=cart_id, id=item_id).first() #Using id=item_id because in the course model we don't have any called item_id instead the field that we have is id which is an invisible field

class CartStatAPIView(generics.RetrieveAPIView):
    serializer_class= api_serializer.CartSerializer
    permission_classes= [AllowAny]
    lookup_field= 'cart_id'

    def get_queryset(self):
        cart_id = self.kwargs['cart_id']
        queryset= api_models.Cart.objects.filter(cart_id=cart_id)
        return queryset
    
    def get(self, request, *args, **kwargs):
        queryset= self.get_queryset()


        total_price= 0.00
        total_tax= 0.00
        main_total= 0.00

        for cart_item in queryset:
            total_price += float(self.calculate_price(cart_item))
            total_tax += float(self.calculate_tax(cart_item))
            main_total += round(float(self.calculate_total(cart_item)), 2)
        
        data= {
            "price": total_price,
            "tax": total_tax,
            "total": main_total,
        }

        return Response(data)
    
    def calculate_price(self, cart_item):
        return cart_item.price
    
    def calculate_tax(self, cart_item):
        return cart_item.tax_fee
    
    def calculate_total(self, cart_item):
        return cart_item.total

class CreateOrderAPIView(generics.CreateAPIView):
    serializer_class= api_serializer.CartOrderSerializer
    permission_classes= [AllowAny]
    queryset= api_models.CartOrder.objects.all()

    def create (self, request, *args, **kwargs):
        full_name= request.data['full_name']
        email= request.data['email']
        country= request.data['country']
        cart_id= request.data['cart_id']
        user_id= request.data['user_id']

        if user_id != 0:
            user= User.objects.get(id=user_id)
        else:
            user= None
        
        cart_items= api_models.Cart.objects.filter(cart_id= cart_id)
        
        total_price= Decimal(0.00)
        total_tax= Decimal(0.00)
        total_initial_total= Decimal(0.00)
        main_total= Decimal(0.00)

        order= api_models.CartOrder.objects.create(
            full_name= full_name,
            email= email,
            country= country,
            student= user
        )

        for c in cart_items:
            api_models.CartOrderItem.objects.create(
                order=order,
                course= c.course,
                price= c.price,
                tax_fee= c.tax_fee,
                total= c.total,
                initial_total= c.total,
                teacher= c.course.teacher

            )

            total_price += Decimal(c.price)
            total_tax += Decimal(c.tax_fee)
            total_initial_total += Decimal(c.total)
            main_total += Decimal(c.total)

            order.teachers.add(c.course.teacher)

        order.sub_total= total_price
        order.tax_fee= total_tax
        order.initial_total= total_initial_total
        order.total= main_total
        order.save()

        return Response({"message": "Order Created Successfully"}, status=status.HTTP_201_CREATED)

class CheckoutAPIView(generics.RetrieveAPIView):
    serializer_class= api_serializer.CartOrderSerializer
    permission_classes= [AllowAny]
    queryset= api_models.CartOrder.objects.all()
    lookup_field= 'order_id'

class CouponApplyAPIView(generics.CreateAPIView):
    serializer_class= api_serializer.CouponSerializer
    permission_classes= [AllowAny]

    def create(self, request, *args, **kwargs):
        order_oid= request.data['order_oid']
        coupon_code= request.data['coupon_code']

        order= api_models.CartOrder.objects.get(order_id= order_oid)
        coupon= api_models.Coupon.objects.get(code= coupon_code)

        if coupon:
            order_items= api_models.CartOrderItem.objects.filter(order=order, teacher= coupon.teacher)
            for o in order_items:
                if not coupon in o.coupons.all():
                    discount= o.total *coupon.discount /100

                    o.total -= discount
                    o.price -= discount
                    o.saved += discount
                    o.applied_coupon= True
                    o.coupons.add(coupon)

                    order.coupons.add(coupon)
                    order.total -= discount
                    order.sub_total -= discount
                    order.saved += discount

                   
                    o.save()
                    order.save()
                    coupon.used_by.add(order.student)
                    return Response({"message": "Coupon code activated"}, status=status.HTTP_201_CREATED)
                else:
                    return Response({"message": "Coupon code already applied"}, status=status.HTTP_200_OK) 
        else:
            return Response({"message": "Coupon code not found"}, status=status.HTTP_404_NOT_FOUND)

class StripeCheckoutAPIView(generics.CreateAPIView):
    serializer_class= api_serializer.CartOrderSerializer
    permission_classes= [AllowAny]

    def create(self, request, *args, **kwargs):
        order_oid= self.kwargs['order_oid']
        order= api_models.CartOrder.objects.get(order_id= order_oid)

        if not order:
            return Response({"message": "Order Not Found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            checkout_session= stripe.checkout.Session.create(
                customer_email= order.email,
                payment_method_types= ['card'],
                line_items= [
                    {
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': order.full_name,
                            },
                            'unit_amount': int(order.total * 100)
                            
                        },
                        'quantity': 1
                    }
                ],
                mode= 'payment',
                success_url= settings.FRONTEND_SITE_URL + 'payment-success/' + order.order_id + '?session_id= {CHECKOUT_SESSION_ID}',
                cancel_url=settings.FRONTEND_SITE_URL + 'payment-failed/'

            )

            print("Checkout Session :", checkout_session )
            order.stripe_session_id= checkout_session.id

            return redirect(checkout_session.url)
        except stripe.error.StripeError as e:
            return Response({"message": f"Something went wrong during payment. Error: {str(e)}"})

def get_access_token(client_id, secret_key):
    token_url= "https://api.sandbox.paypal.com/v1/oauth/token"
    data={'grant_type': 'client_credentials'}
    auth= (client_id, secret_key)
    response= requests.post(token_url, data=data, auth=auth)

    if response.status_code == 200:
        print("Access Token ====", response.json()['access_token'] )
        return response.json()['access_token']
    else:
        raise Exception(f"Failed to get access token from paypal {response.status_code}")







        


    

# Create your views here.
