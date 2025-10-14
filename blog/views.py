from django.shortcuts import render, get_object_or_404
from .models import BlogPost

def blog_list(request):
    posts = BlogPost.objects.all().order_by('-created_at')
    return render(request, 'blog/list.html', {'posts': posts})

def blog_detail(request, pk):
    post = get_object_or_404(BlogPost, pk=pk)
    return render(request, 'blog/detail.html', {'post': post})
