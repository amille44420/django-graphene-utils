from .forms import ReduceMixinForm

__all__ = ['ReduceMixin']

"""
Mutation mixin to work with form applying the ReduceMixinForm
"""


class ReduceMixin(object):
    def get_form_kwargs(self, root, args, context, info):
        # ensure we can do it
        assert issubclass(self._meta.form_class, ReduceMixinForm)
        # get original keyword arguments
        kwargs = super(ReduceMixin, self).get_form_kwargs(root, args, context, info)
        # reduce the fields to the data we got in
        kwargs['reduce_to'] = (kwargs.get('data', None) or {}).keys()

        return kwargs
