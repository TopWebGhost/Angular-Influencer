'''
views for 'widgets' tab (not to be confused with internal representation of modular portions of a page, known as widgets)
NOTE: must provide 'widgets_page' tpl_var so the header knows which tab to select
'''
from debra.widgets import WishlistItemsFeed, ShelvesFeed
from debra.constants import GRID_COLLAGE, SEO_VALUES
from debra.models import UserProfile, Lottery, LotteryTask, LotteryPrize, LotteryEntry, LotteryEntryCompletedTask, Embeddable
from debra.forms import CreateLotteryForm, LotteryPrizeForm, LotteryTaskForm, EnterLotteryForm
from debra.decorators import user_is_page_user
from django.contrib.auth.forms import PasswordResetForm
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.db.models import Sum
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.template import RequestContext
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from datetime import datetime
from debra import search_helpers
import pdb
import json

@login_required
@user_is_page_user
def widgets_home(request, user=0):
    ### redirecting to home
    redirect(reverse('debra.account_views.brand_home'))
    page_user_prof = UserProfile.objects.get(id=user)


    return render(request, 'pages/widgets/home.html', {
            'widgets_page': True,
            'page_title': SEO_VALUES['widgets_home']['title'],
            'meta_description': SEO_VALUES['widgets_home']['meta_desc']
        }, context_instance=RequestContext(request))

@login_required
@user_is_page_user
def new_lottery(request, user=0):
    return render(request, 'pages/widgets/new_lottery.html', {
            'widgets_page': True,
            'widget_type': "lottery",
            'create_lottery_form': CreateLotteryForm(),
            'create_prize_form': LotteryPrizeForm(),
            'create_task_form': LotteryTaskForm(),
            'themes_for_template':  Lottery.THEME_CHOICES,
            'tasks_for_template':  LotteryTask.ALL_TASKS,
            'points_for_template':  LotteryTask.POINT_VALUES,
            'page_title': SEO_VALUES['new_lottery']['title'],
            'meta_description': SEO_VALUES['new_lottery']['meta_desc']
        }, context_instance=RequestContext(request))

@login_required
@user_is_page_user
def edit_lottery(request, user=0, lottery=0):
    lottery = Lottery.objects.get(id=lottery)
    prizes = lottery.self_prizes
    tasks = lottery.self_tasks.order_by('step_id')
    return render(request, 'pages/widgets/new_lottery.html', {
        'widgets_page': True,
        'widget_type': "lottery",
        'edit_mode': True,
        'lottery': lottery,
        'embeddable_url': reverse('debra.widget_views.render_embeddable', args=(user, lottery.self_embeddable.id,)),
        'created_prizes': [{'prize': prize, 'form': LotteryPrizeForm(instance=prize)} for prize in prizes],
        'created_tasks': [{'task': task, 'form': LotteryTaskForm(instance=task)} for task in tasks],
        'create_lottery_form': CreateLotteryForm(instance=lottery, initial={
            'start_date': lottery.start_datetime.date(),
            'start_time': lottery.start_datetime.time(),
            'end_date': lottery.end_datetime.date(),
            'end_time': lottery.end_datetime.time()
        }),
        'create_prize_form': LotteryPrizeForm(),
        'create_task_form': LotteryTaskForm(),
        'themes_for_template':  Lottery.THEME_CHOICES,
        'tasks_for_template':  LotteryTask.ALL_TASKS,
        'points_for_template':  LotteryTask.POINT_VALUES,
        'page_title': SEO_VALUES['edit_lottery']['title'],
        'meta_description': SEO_VALUES['edit_lottery']['meta_desc']
    }, context_instance=RequestContext(request))

@login_required
@user_is_page_user
def preview_lottery(request, user=0, lottery=0):
    lottery = Lottery.objects.get(id=lottery)

    return render(request, 'pages/widgets/preview_lottery.html', {
        'widgets_page': True,
        'widget_type': "lottery",
        'lottery': lottery,
        'embeddable_url': reverse('debra.widget_views.render_embeddable', args=(lottery.creator.id, lottery.self_embeddable.id,)),
        'page_title': SEO_VALUES['preview_lottery']['title'],
        'meta_description': SEO_VALUES['preview_lottery']['meta_desc']
    }, context_instance=RequestContext(request))

@login_required
@user_is_page_user
def lottery_analytics(request, user=0, lottery=0):
    lottery = Lottery.objects.get(id=lottery)

    return render(request, 'pages/widgets/lottery_analytics.html', {
        'widgets_page': True,
        'widget_type': "lottery",
        'lottery': lottery,
        'lottery_winners': lottery.self_winners,
        'num_participants': lottery.self_entries.count(),
        'average_tasks': lottery.average_num_tasks_completed,
        'time_remaining': lottery.time_remaining_dict,
        'entries': lottery.self_completed_tasks.select_related('entry', 'entry__user', 'entry__user__user', 'task').order_by('id'),
        'page_title': SEO_VALUES['lottery_analytics']['title'],
        'meta_description': SEO_VALUES['lottery_analytics']['meta_desc']
    }, context_instance=RequestContext(request))

@login_required
@user_is_page_user
def view_lotterys(request, user=0):
    page_user_prof = UserProfile.objects.get(id=user)

    return render(request, 'pages/widgets/all_lotterys.html', {
        'widgets_page': True,
        'widget_type': "lottery",
        'lottery_home': True,
        'finished_lotterys': page_user_prof.created_lotterys.filter(end_datetime__lt=datetime.now()).order_by("-id"),
        'current_lotterys': page_user_prof.created_lotterys.filter(end_datetime__gte=datetime.now()).order_by("-id"),
        'created_lotterys': page_user_prof.created_lotterys.order_by("-id"),
        'page_title': SEO_VALUES['view_lotterys']['title'],
        'meta_description': SEO_VALUES['view_lotterys']['meta_desc']
    }, context_instance=RequestContext(request))

@login_required
@user_is_page_user
def collage(request, user=0, collage_type=GRID_COLLAGE):
    page_user_prof = UserProfile.objects.get(id=user)

    if request.is_ajax():
        return WishlistItemsFeed(request, {"shelf": request.GET.get('q')}, item_tpl='collage_product.html', ajax_request=True, user=page_user_prof).generate_items().render()
    else:
        return render(request, 'pages/widgets/collage.html', {
            'widgets_page': True,
            'sidebar': ShelvesFeed(request, request.GET.get('q', None),
                                   view_file="collage_shelves.html",
                                   user=page_user_prof,
                                   qs=page_user_prof.user_created_shelves | page_user_prof.user_category_shelves).render(),
            'collage_type': collage_type,
            'page_title': SEO_VALUES['collage']['title'],
            'meta_description': SEO_VALUES['collage']['meta_desc']
        }, context_instance=RequestContext(request))


#####-----< Non Rendering Methods >-----#####
@login_required
def create_lottery(request, user=0):
    '''
    this view method is for creating the initial lottery object
    '''
    page_user_prof = UserProfile.objects.get(id=user)
    lottery_id = request.POST.get('exists_id', None)
    lottery_form = CreateLotteryForm(data=request.POST, instance=Lottery.objects.get(id=lottery_id) if lottery_id else None)
    if lottery_form.is_valid():
        lottery_instance = lottery_form.save(commit=False)
        lottery_instance.creator = page_user_prof
        lottery_instance.start_datetime = lottery_form.cleaned_data['start_datetime']
        lottery_instance.end_datetime = lottery_form.cleaned_data['end_datetime']
        lottery_instance.save()
        return HttpResponse(content=json.dumps({
            'exists_id': lottery_instance.id,
            'giveaway_name': lottery_instance.name,
            'create_task_url': reverse('debra.widget_views.create_lottery_task', args=(user, lottery_instance.id)),
            'create_prize_url': reverse('debra.widget_views.create_lottery_prize', args=(user, lottery_instance.id)),
            'preview_url': reverse('debra.widget_views.preview_lottery', args=(user, lottery_instance.id))
        }))

@login_required
def duplicate_lottery(request, user=0, lottery=0):
    '''
    this view method duplicates an existing lottery, which means the new lottery contains the same prizes, tasks, name, etc.
    Basically only thing that changes is the start / end date
    '''
    user = UserProfile.objects.get(id=user)
    lottery = Lottery.objects.get(id=lottery)

    tasks = lottery.self_tasks
    prizes = lottery.self_prizes
    embeddable = lottery.self_embeddable

    lottery.clone()
    lottery.duplicate(tasks, prizes, embeddable)

    return redirect(reverse('debra.widget_views.edit_lottery', args=(user.id, lottery.id,)))


@login_required
def create_lottery_prize(request, user=0, lottery=0):
    '''
    this view method is for creating lottery prizes
    '''
    form = LotteryPrizeForm(request.POST)

    # if the form has already been submitted in this session, then the exists_id will exist and we get the appropriate
    # model instance for the modelform
    prize_id = request.POST.get('exists_id', None)
    if prize_id and prize_id != '':
        form.instance = LotteryPrize.objects.get(id=prize_id)

    if form.is_valid():
        prize_obj = form.save(commit=False)
        lottery_obj = Lottery.objects.get(id=lottery)
        prize_obj.lottery = lottery_obj
        prize_obj.save()

        response = {
            'id': prize_obj.id,
            'description': prize_obj.description,
            'brand': prize_obj.brand,
            'quantity': prize_obj.quantity,
            'deleteUrl': reverse('delete_lottery_prize', args=(user, lottery, prize_obj.id))
        }
        return HttpResponse(content=json.dumps(response), status=200)
    else:
        return HttpResponse(status=500)

@login_required
def create_lottery_task(request, user=0, lottery=0):
    '''
    this view method is for creating lottery tasks
    Note: I know that this and create_lottery_prize are currently near identical. The reason they are separate is
    because we see each evolving in separate directions
    '''
    form = LotteryTaskForm(request.POST)

    # if the form has already been submitted in this session, then the exists_id will exist and we get the appropriate
    # model instance for the modelform
    task_id = request.POST.get('exists_id', None)
    task = LotteryTask.objects.get(id=task_id) if task_id and task_id != '' else None
    if task:
        form.instance = LotteryTask.objects.get(id=task_id)

    if form.is_valid():
        task_obj = form.save(commit=False)
        lottery_obj = Lottery.objects.get(id=lottery)
        task_obj.lottery = lottery_obj

        # if there is no task (this is a newly created task) then set this new task's step_id to the number of lotterytasks
        task_obj.step_id = LotteryTask.objects.count() if not task else task_obj.step_id
        task_obj.save()

        response = {
            'id': task_obj.id,
            'taskName': task_obj.task,
            'points': task_obj.point_value,
            'mandatory': task_obj.mandatory,
            'deleteUrl': reverse('delete_lottery_task', args=(user, lottery, task_obj.id))
        }
        return HttpResponse(content=json.dumps(response), status=200)
    else:
        return HttpResponse(status=500, content=json.dumps({'errors': form.errors}))

@login_required
def delete_lottery_modifier(request, user=0, lottery=0, item=0, modifier="task"):
    '''
    this view method is for deleting either lottery prizes or tasks
    '''
    to_delete = LotteryTask.objects.get(id=item) if modifier == "task" else LotteryPrize.objects.get(id=item)
    to_delete.delete()
    return HttpResponse(status=200)

@login_required
def pick_winner(request, user=0, lottery=0):
    '''
    this view method is for choosing the winner(s) of a lottery
    '''
    lottery = Lottery.objects.get(id=lottery)
    winner = lottery.pick_winner()
    return HttpResponse(status=200, content=json.dumps({
        'id': winner.id,
        'email': winner.entry.user.user.email,
        'email_url': reverse('debra.email_views.lottery_winner', args=(winner.entry.user.id, lottery.id,)),
        'task': winner.task.task_dict['value'](""),
        'target': winner.task.url_target_name,
        'winning_num': winner.task_num,
        'delete_url': reverse('debra.widget_views.delete_winner', args=(user, lottery.id, winner.id,))
    }))

@login_required
def delete_winner(request, user=0, lottery=0, winner=0):
    '''
    this view method is for deleting a winner from the lottery
    '''
    winner = LotteryEntryCompletedTask.objects.get(id=winner)
    winner.is_winner = False
    winner.save()
    return HttpResponse(status=200)

@login_required
def show_winners(request, user=0, lottery=0):
    '''
    when the user has picked winnners for the lottery and wants their picks to be viewable on the embeddable,
    this view method is called which sets the lottery's show_winners flag to true
    '''
    lot = Lottery.objects.get(id=lottery)
    lot.show_winners = True
    lot.save()
    return HttpResponse(status=200)

@login_required
def clear_test_entries(request, user=0, lottery=0):
    '''
    this method is called when the creator of a lottery decides to reset the test entries on their lottery
    '''
    lot = Lottery.objects.get(id=lottery)
    lot.clear_test_entries()
    return redirect(request.GET.get('next'))
#####-----</ Non Rendering Methods >-----#####

#####-----< Embeddables Methods >-----#####
@login_required
def enter_lottery_task(request, user=0, embeddable=0):
    '''
    this view method creates a LotteryEntryCompletedTask
    Note: this function receives a JSON array of entered LotteryTask having structure
    {
        id: <id>,
        extra: <text> (this can either map to the custom task response for a custom task, or validation url for a non-custom task)
        (optional) completed_id: <text> (if the completed task is being edited in the same session, this will be set)
    }
    '''
    page_user_prof=UserProfile.objects.get(id=user)
    embeddable = Embeddable.objects.get(id=embeddable)
    lottery = embeddable.lottery
    # get the lottery entry for this user or create a new one if it doesnt exist
    entry = LotteryEntry.objects.get_or_create(user=page_user_prof, lottery=lottery)[0]

    task = json.loads(request.raw_post_data)
    task_obj = LotteryTask.objects.get(id=task.get('id'))
    extra = task.get('extra', None)
    completed_task = task.get('completed_id', None)

    # there will be a completed task if we're editing a lottery entry completed task in the same session
    if completed_task:
        completed_task = LotteryEntryCompletedTask.objects.get(id=completed_task)
        completed_task.entry_validation = extra if task_obj.task_dict != LotteryTask.CUSTOM else None
        completed_task.custom_task_response = extra if task_obj.task_dict == LotteryTask.CUSTOM else None
        completed_task.save()
    else:
        completed_task = LotteryEntryCompletedTask.objects.create(entry=entry, task=task_obj,
                                                 entry_validation=extra if task_obj.task_dict != LotteryTask.CUSTOM else None,
                                                 custom_task_response=extra if task_obj.task_dict == LotteryTask.CUSTOM else None)

    return HttpResponse(content=json.dumps({
        'embeddable_url': reverse('debra.widget_views.render_embeddable', args=(lottery.creator.id, embeddable.id,)),
        'completed_id': completed_task.id
    }))

@login_required
def create_embeddable(request, user=0, type=Embeddable.COLLAGE_WIDGET):
    '''
    this view method creates embeddables that may be embedded on other sites, it returns a url
    to the render method for the created embeddable
    '''
    user_prof = UserProfile.objects.get(id=user)
    lottery = None

    if type == Embeddable.COLLAGE_WIDGET:
        html = request.POST.get('html')
    else:
        lottery = Lottery.objects.get(id=request.POST.get('lottery_id'))
        html = ""  #has to be dynamically generated each time anyways, no sense in rendering now

    embeddable = Embeddable.objects.get_or_create(creator=user_prof, lottery=lottery, html=html, type=type)[0]
    return HttpResponse(status=200, content=json.dumps({
        'embeddable_url': reverse('debra.widget_views.render_embeddable', args=(user, embeddable.id,))
    }))

def render_embeddable(request, creator=0, embeddable=0):
    ### re-directing to home
    return redirect(reverse('debra.account_views.brand_home'))
    try:
        embeddable = Embeddable.objects.get(id=embeddable)
    except ObjectDoesNotExist:
        return render(request, 'embeddables/renderable.html', {
            'renderable_404': True,
            'hide_header': True
        }, context_instance=RequestContext(request))

    request_user = request.user.userprofile if request.user and request.user.is_authenticated() else None
    type = embeddable.type
    # if the type is a lottery widget, we cant use anything we've stored in the db because that data will be stale
    if type == Embeddable.LOTTERY_WIDGET:
        lottery = embeddable.lottery

        # if the lottery is in test mode, we have to check if its started and - if it has - remove test mode True and destroy completed entries
        if lottery.in_test_mode and lottery.is_running:
            lottery.clear_test_mode()

        completed_tasks = request_user.completed_lottery_tasks(lottery) if request_user else []
        incomplete_tasks = request_user.incomplete_lottery_tasks(lottery).order_by('-mandatory', 'step_id') if request_user else []
        all_tasks = lottery.self_tasks.order_by('-mandatory', 'step_id')
        mandatory_tasks = all_tasks.filter(mandatory=True)
        bonus_tasks = all_tasks.filter(mandatory=False)

        points_available = mandatory_tasks.aggregate(Sum('point_value'))['point_value__sum'] if mandatory_tasks else 0
        bonus_points_available = bonus_tasks.aggregate(Sum('point_value'))['point_value__sum'] if bonus_tasks else 0
        all_points_available = points_available + bonus_points_available

        html = render_to_string('embeddables/lottery.html', {
            'time_remaining': lottery.time_remaining_dict,
            'finished_mandatory': request_user.completed_mandatory_tasks(lottery) if request_user else False,
            'finished_everything': len(completed_tasks) == len(all_tasks),
            'lottery': lottery,
            'enter_lottery_form': EnterLotteryForm(),
            'embeddable': embeddable,
            'completed_tasks': completed_tasks,
            'last_incomplete_task': incomplete_tasks[len(incomplete_tasks) - 1] if request_user and len(incomplete_tasks) > 0 else 0,
            'tasks': all_tasks,
            'prizes': lottery.self_prizes,
            'completed_points': completed_tasks.aggregate(Sum('point_value'))['point_value__sum'] if completed_tasks else 0,
            'points_available': points_available,
            'bonus_points_available': bonus_points_available,
            'all_points_available': all_points_available,
            'all_points_completed': lottery.total_points_completed if lottery.total_points_completed else 0,
            'winners': lottery.self_completed_tasks.filter(is_winner=True).select_related('entry', 'entry__user', 'entry__user__user') if lottery.show_winners else None,
            'user': request_user if request_user else None
        }, context_instance=RequestContext(request))
    else:
        html = render_to_string('embeddables/collage.html', {
            'html': embeddable.html
        }, context_instance=RequestContext(request))

    response = render(request, 'embeddables/renderable.html', {
        'html': html,
        'hide_header': True,
        'embeddable_id': embeddable.id,
        'embeddable_type': embeddable.type,
        'password_reset_form': PasswordResetForm(),
        'next': reverse('debra.widget_views.render_embeddable', args=(creator, embeddable.id,)),
        'page_title': SEO_VALUES['embeddable']['title'],
        'meta_description': SEO_VALUES['embeddable']['meta_desc']
    }, context_instance=RequestContext(request))

    return response
#####-----</ Embeddables Methods >-----#####
