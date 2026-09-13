from django.shortcuts import render
from django.http import FileResponse, Http404
from django.conf import settings
import os

def index(request):
    return render(request, 'website/index.html')

def download_app(request):
    """Отдаёт файл установщика программы."""
    file_path = settings.DOWNLOAD_FILE_PATH
    
    if not os.path.exists(file_path):
        raise Http404("Файл не найден")
    
    response = FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename='pvz_setup.exe'
    )
    return response