from django.views.generic import View

from debra.decorators import cached_property


class BaseView(View):

    def set_params(self, request, *args, **kwargs):
        self.user = request.user

    def get_section_switchers(self):
        return {}

    @property
    def context(self):
        print '** BaseView'
        context = {}
        context.update(self.section_switchers)
        return context

    @cached_property
    def section_switchers(self):
        return self.get_section_switchers()


class BaseTableViewMixin(object):

    def set_params(self, request, *args, **kwargs):
        super(BaseTableViewMixin, self).set_params(request, *args, **kwargs)
        self.request = request
        self.page = int(request.GET.get('page', 1))
        self.sort_by = int(request.GET.get('sort_by', 0))
        self.sort_direction = int(request.GET.get('sort_direction', 0))
        self.paginate_by = int(request.GET.get('paginate_by', 30))

        self.include_total = False
        self.total_with_fields = False

    @cached_property
    def shelf_user(self):
        try:
            shelf_user = self.request.user.userprofile
        except AttributeError:
            shelf_user = None
        return shelf_user

    @property
    def context(self):
        print '** BaseTableViewMixin'
        from debra.serializers import count_totals
        context = super(BaseTableViewMixin, self).context
        context.update({
            'sort_by': self.sort_by,
            'sort_direction': self.sort_direction,
            'search_page': True,
            'type': 'followed',
            'shelf_user': self.shelf_user,
            'request': self.request,
            'paginated_queryset': self.paginated_queryset,
            'paginated_data_list': self.serialized_data['data_list'],
            'headers': self.headers,
            'fields': self.fields,
            'fields_loading': self.serializer_class.POST_RELATED_FIELDS,
            'fields_unsortable': self.serializer_class.UNSORTABLE_FIELDS,
            'fields_hidden': self.hidden_fields,
            'sorting_params': self.cleaned_sorting_get_params,
            'rows_number': len(
                set(x for x, _ in self.fields) - set(self.fields)),
            'data_count': self.paginated_queryset.paginator.count,
            'counts': self.counts,
        })
        if self.include_total:
            context.update(
                count_totals(
                    self.ordered_queryset,
                    self.serializer_class,
                    self.total_with_fields
                )
            )
        return context

    @property
    def counts(self):
        return {}

    @cached_property
    def order_params(self):
        return []

    @cached_property
    def default_order_params(self):
        return []

    @cached_property
    def order_by(self):
        from debra.search_helpers import sorting_options
        return self.order_params + list(
            sorting_options(
                (self.sort_by, self.sort_direction),
                self.serializer_class,
                self.annotation_fields,
                default_params=self.default_order_params,
                hidden_fields=self.hidden_fields,
            )
        )

    @cached_property
    def distinct(self):
        return []

    @cached_property
    def limit(self):
        pass

    @cached_property
    def annotation_fields(self):
        return

    @cached_property
    def distinct_fields(self):
        return []

    @cached_property
    def serializer_class(self):
        raise NotImplementedError

    @cached_property
    def serializer_context(self):
        return {
            'brand': self.request.visitor["base_brand"],
            'request': self.request,
        }

    @cached_property
    def queryset(self):
        raise NotImplementedError

    @cached_property
    def filtered_queryset(self):
        return self.queryset

    @cached_property
    def annotated_queryset(self):
        return self.filtered_queryset

    @cached_property
    def ordered_queryset(self):
        qs = self.annotated_queryset.order_by(*self.order_by)
        if self.distinct:
            qs = qs.distinct(*self.distinct)
        if self.limit:
            qs = qs[:self.limit]
        return qs

    @cached_property
    def paginated_queryset(self):
        from debra.helpers import paginate
        p = paginate(
            self.ordered_queryset,
            page=self.page,
            paginate_by=self.paginate_by,
            count=self.counts['current'],
        )
        return p

    @cached_property
    def serialized_data(self):
        from debra.serializers import serialize_post_analytics_data
        self.pre_serialize_processor()
        return serialize_post_analytics_data(
            self.paginated_queryset, self.serializer_class,
            serializer_context=self.serializer_context
        )

    @cached_property
    def hidden_fields(self):
        return self.serializer_class.HIDDEN_FIELDS

    @cached_property
    def visible_columns(self):
        return []

    @cached_property
    def serializer_class_level_context(self):
        return {
            'request': self.request,
        }

    @cached_property
    def fields(self):
        return self.serializer_class.get_visible_fields(self.hidden_fields,
            context=self.serializer_class_level_context)

    @cached_property
    def headers(self):
        return self.serializer_class.get_headers(self.hidden_fields,
            self.visible_columns, context=self.serializer_class_level_context)

    @cached_property
    def cleaned_sorting_get_params(self):
        sorting_params = self.request.GET.copy()
        if 'sort_direction' in sorting_params:
            del sorting_params['sort_direction']
        if 'sort_by' in sorting_params:
            del sorting_params['sort_by']
        if 'page' in sorting_params:
            del sorting_params['page']
        return sorting_params

    def pre_serialize_processor(self):
        pass
