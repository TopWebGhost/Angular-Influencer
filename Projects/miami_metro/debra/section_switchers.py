from debra.helpers import PageSectionSwitcher
from debra.decorators import cached_property


class SectionSwitcherWrapper(object):

    DISABLED_SECTIONS = []  

    def __init__(self, queryset, selected_section_value=None,
            context=None, child_switchers=None):
        self._queryset = queryset
        self._selected_section_value = selected_section_value
        self._context = context or {}
        self.child_switchers = child_switchers or {}
        self._switcher = PageSectionSwitcher(**self.to_dict())

    @cached_property
    def queryset(self):
        return self._queryset

    @property
    def sections(self):
        raise NotImplementedError

    @property
    def hidden(self):
        pass

    @property
    def counts(self):
        pass

    @property
    def ulrs(self):
        pass

    @property
    def extra(self):
        pass

    @property
    def url_args(self):
        pass

    @property
    def extra_url_args(self):
        pass

    @cached_property
    def default_selected_section_value(self):
        if self._switcher.first_non_empty_section:
            return self._switcher.first_non_empty_section.key
        return self._switcher.first_visible_section.key

    @cached_property
    def selected_section_value(self):
        if self._selected_section_value is None:
            return self.default_selected_section_value
        return self._selected_section_value

    def to_dict(self):
        return dict(
            sections=self.sections,
            selected_section=None,
            urls=self.urls,
            extra=self.extra,
            hidden=self.hidden,
            counts=self.counts,
            url_args=self.url_args,
            extra_url_args=self.extra_url_args,
            wrapper=self,
        )

    @cached_property
    def switcher(self):
        self._switcher.switch(self.selected_section_value)
        return self._switcher
