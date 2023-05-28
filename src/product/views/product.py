import json

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.views import generic
from django.views.decorators.csrf import csrf_exempt

from product.models import Variant, Product, ProductVariantPrice, ProductVariant, ProductImage
from product.forms import ProductCreateForm, ProductImageCreateForm, ProductVariantCreateForm, \
    ProductVariantPriceCreateForm
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status


class CreateProductView(generic.TemplateView):
    template_name = 'products/create.html'

    def get_context_data(self, **kwargs):
        context = super(CreateProductView, self).get_context_data(**kwargs)
        variants = Variant.objects.filter(active=True).values('id', 'title')
        context['product'] = True
        context['variants'] = list(variants.all())
        return context


class UpdateProductView(generic.UpdateView):
    template_name = 'products/update.html'
    model = Product
    fields = ["title", "sku", "description"]

    def get_object(self):
        pk = self.kwargs.get("pk", None)
        if not pk:
            pass
        product_obj = Product.objects.get(pk=pk)
        return product_obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_price_variant_qs = ProductVariantPrice.objects.filter(product=context["object"])
        variant_list = []
        price_variant_list = []
        image_list = []
        for image in ProductImage.objects.filter(product=context["object"]):
            image_list.append(image.file_path)
        for product_price in product_price_variant_qs:
            title = product_price.product_variant_one.variant_title if product_price.product_variant_one else ""
            title += "/" + product_price.product_variant_two.variant_title if product_price.product_variant_two else ""
            title += "/" + product_price.product_variant_three.variant_title if product_price.product_variant_three else ""
            product_variant_data = {
                "id": product_price.id,
                "title": title,
                "price": product_price.price,
                "stock": product_price.stock,
            }
            price_variant_list.append(product_variant_data)

        variant_qs = Variant.objects.all().distinct()
        for variant in variant_qs:
            variant_data = {
                "option": variant.id,
                "tags": []
            }
            for product_variant in ProductVariant.objects.filter(product=context["object"], variant=variant):
                variant_data["tags"].append(product_variant.variant_title)
            variant_list.append(variant_data)

        product_data = {
            "id": context["object"].id,
            "product_name": context["object"].title,
            "product_sku": context["object"].sku,
            "description": context["object"].description,
            "product_image": image_list,
            "product_variant_prices": price_variant_list,
            "product_variant": variant_list
        }
        variants = Variant.objects.filter(active=True).values('id', 'title')
        context["product"] = product_data
        context["variants"] = list(variants.all())
        return context


class ProductListView(generic.ListView):
    template_name = 'products/list.html'
    queryset = Product.objects.all()
    paginate_by = 10  # Set the number of products to display per page

    def get_queryset(self):
        queryset = Product.objects.all()
        # Retrieve filter parameters from the request
        title = self.request.GET.get('title', None)
        price_from = self.request.GET.get('price_from', None)
        price_to = self.request.GET.get('price_to', None)
        variant = self.request.GET.get('variant', None)
        date = self.request.GET.get('date', None)
        # Apply filters to the queryset
        if title:
            self.queryset = queryset.filter(title__icontains=title)

        # filter with price
        if price_from and price_to:
            product_variant_qs = ProductVariantPrice.objects.filter(price__range=[price_from, price_to]).values(
                'product')
            product_ids = []
            for variant_ids in product_variant_qs:
                if not variant_ids["product"] in product_ids:
                    product_ids.append(variant_ids["product"])
            self.queryset = queryset.filter(id__in=product_ids)

        # filter with color
        if variant:
            product_variant_qs = ProductVariantPrice.objects.filter(
                Q(product_variant_one__variant_title=variant) |
                Q(product_variant_two__variant_title=variant) |
                Q(product_variant_three__variant_title=variant)
            ).values(
                'product')
            product_ids = []
            for variant_ids in product_variant_qs:
                if not variant_ids["product"] in product_ids:
                    product_ids.append(variant_ids["product"])
            self.queryset = queryset.filter(id__in=product_ids)
        if date:
            self.queryset = queryset.filter(created_at__date=date)

        return self.queryset.distinct()

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        product_list_data = []
        variant_qs = ProductVariant.objects.all().values("variant_title").distinct()
        for product in context["product_list"]:
            product_variant_qs = ProductVariantPrice.objects.filter(product=product)
            variant_list = []
            for product_variant in product_variant_qs:
                variant_data = {
                    "product_variant_one": product_variant.product_variant_one.variant_title
                    if product_variant.product_variant_one else "",
                    "product_variant_two": product_variant.product_variant_two.variant_title
                    if product_variant.product_variant_two else "",
                    "product_variant_three": product_variant.product_variant_three.variant_title
                    if product_variant.product_variant_three else "",
                    "price": product_variant.price,
                    "stock": product_variant.stock,
                }
                variant_list.append(variant_data)
            product_data = {
                "id": product.id,
                "title": product.title,
                "created_at": product.created_at,
                "description": product.description,
                "product_variant": variant_list
            }
            product_list_data.append(product_data)

        paginator = Paginator(context["product_list"], self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context["variant_qs"] = variant_qs
        context["products"] = page_obj
        context["product_data"] = product_list_data
        context["pagination_details"] = self.get_pagination_details(page_obj, paginator)
        return context

    def get_pagination_details(self, page_obj, paginator):
        current_page = self.request.GET.get('page', 1)
        start_index = (int(current_page) - 1) * paginator.per_page + 1
        if paginator.count < 1:
            start_index = 0
        end_index = start_index + paginator.object_list.count() - 1
        if paginator.count < 1:
            end_index = 0
        return f"Showing {start_index} to {end_index} out of {self.queryset.count()}"


class CreateProductAPIView(APIView):
    @transaction.atomic
    # @csrf_exempt
    def post(self, request, *args, **kwargs):
        file_path = request.FILES.getlist("product_image")
        sku = request.data.get("sku", None)
        variants = request.data.get("product_variant", [])
        product_variant_prices = request.data.get("product_variant_prices", [])

        if Product.objects.filter(sku=sku).exists():
            return Response({"details": "Product SKU already exists"}, status=status.HTTP_400_BAD_REQUEST)

        product_form = ProductCreateForm(request.data)
        if product_form.is_valid():
            product_obj = product_form.save()

            # Manage product images
            for file in file_path:
                data = dict()
                data["file_path"] = file
                data["product"] = product_obj
                product_image_form = ProductImageCreateForm(data)
                if product_image_form.is_valid():
                    product_image_form.save()

            # Manage product variants
            if variants:
                for variant in variants:
                    variant_list = []
                    variant_id = variant["option"]
                    for tag_name in variant["tags"]:
                        data = dict()
                        data["variant_title"] = tag_name
                        data["variant"] = Variant.objects.filter(pk=variant_id).first()
                        data["product"] = product_obj
                        product_variant_form = ProductVariantCreateForm(data)
                        if product_variant_form.is_valid():
                            product_variant_obj = product_variant_form.save()
                            variant_list.append(product_variant_obj)
                for variant_prices in product_variant_prices:
                    variant_names = variant_prices["title"].split("/")
                    price_data = {
                        "product": product_obj,
                        "product_variant_one": ProductVariant.objects.filter(
                            variant_title=variant_names[0],
                            product=product_obj).first() if len(variant_names) >= 1 else None,
                        "product_variant_two": ProductVariant.objects.filter(
                            variant_title=variant_names[1],
                            product=product_obj).first() if len(variant_names) >= 2 else None,
                        "product_variant_three": ProductVariant.objects.filter(
                            variant_title=variant_names[2],
                            product=product_obj).first() if len(variant_names) >= 3 else None,
                        "price": variant_prices["price"] if variant_prices["price"] else 0,
                        "stock": variant_prices["stock"] if variant_prices["stock"] else 0,
                    }
                    product_price_form = ProductVariantPriceCreateForm(price_data)
                    if product_price_form.is_valid():
                        product_price_form.save()
        else:
            return Response({"details": "Invalid product data"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"details": "Product created"}, status=status.HTTP_201_CREATED)


class UpdateProductAPIView(APIView):
    def post(self, request, *args, **kwargs):
        pk = kwargs.get("pk", None)
        if not pk:
            return HttpResponseBadRequest("Invalid input")

        file_path = request.FILES.getlist("file_path")
        sku = request.data.get("sku", None)
        variants = request.data.get("product_variant", [])
        product_variant_prices = request.data.get("product_variant_prices", [])

        if Product.objects.filter(~Q(pk=pk), sku=sku).exists():
            return Response({"details":"Product SKU already exists"}, status=status.HTTP_400_BAD_REQUEST)

        product_obj = Product.objects.filter(pk=pk).first()
        all_product_variant = list(ProductVariant.objects.filter(product=product_obj).values_list('id', flat=True))

        all_product_prices = list(ProductVariantPrice.objects.filter(product=product_obj).values_list('id', flat=True))
        product_form = ProductCreateForm(request.data, instance=product_obj)
        if product_form.is_valid():
            product_obj = product_form.save()

            # Manage product images
            for file in file_path:
                data = dict()
                data["file_path"] = file
                data["product"] = product_obj
                product_image_form = ProductImageCreateForm(data)
                if product_image_form.is_valid():
                    product_image_form.save()

            # Manage product variants
            if variants:
                for variant in variants:
                    variant_id = variant["option"]
                    variant_list = []
                    for tag_name in variant["tags"]:
                        data = dict()
                        data["variant_title"] = tag_name
                        data["variant"] = Variant.objects.filter(pk=variant_id).first()
                        data["product"] = product_obj
                        product_variant_obj = ProductVariant.objects.filter(**data).first()
                        if product_variant_obj:
                            variant_list.append(product_variant_obj)
                        else:
                            product_variant_form = ProductVariantCreateForm(data)
                            if product_variant_form.is_valid():
                                product_variant_obj = product_variant_form.save()
                                variant_list.append(product_variant_obj)
                            print(product_variant_form.errors)

                        if product_variant_obj.id in all_product_variant:
                            all_product_variant.remove(product_variant_obj.id)

                    # manage product price data
                for variant_prices in product_variant_prices:
                    print(variant_prices, 'variant_prices')
                    product_price_id = variant_prices.get('id', None)
                    variant_names = variant_prices["title"].split("/")
                    price_data = {
                        "product": product_obj,
                        "product_variant_one": ProductVariant.objects.filter(
                            variant_title=variant_names[0],
                            product=product_obj).first() if len(variant_names) >= 1 else None,
                        "product_variant_two": ProductVariant.objects.filter(
                            variant_title=variant_names[1],
                            product=product_obj).first() if len(variant_names) >= 2 else None,
                        "product_variant_three": ProductVariant.objects.filter(
                            variant_title=variant_names[2],
                            product=product_obj).first() if len(variant_names) >= 3 else None,
                        "price": variant_prices["price"] if variant_prices["price"] else 0,
                        "stock": variant_prices["stock"] if variant_prices["stock"] else 0,
                    }

                    if product_price_id:
                        all_product_prices.remove(product_price_id)
                        product_price_obj = ProductVariantPrice.objects.filter(pk=product_price_id).first()
                        product_price_form = ProductVariantPriceCreateForm(price_data, instance=product_price_obj)
                    else:
                        product_price_form = ProductVariantPriceCreateForm(price_data)
                    if product_price_form.is_valid():
                        product_price_form.save()
                    print(product_price_form.errors, 'shfjsdhfi')


                # remove not using variants
                for variant_id in all_product_variant:
                    product_variant_obj = ProductVariant.objects.filter(pk=variant_id).first()
                    if product_variant_obj:
                        product_variant_obj.delete()

            return Response({"details": "Product updated"}, status=status.HTTP_200_OK)
        else:
            print(product_form.errors)
            return Response({"details": "Invalid product data"}, status=status.HTTP_400_BAD_REQUEST)

