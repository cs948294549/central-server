from flask import Flask, request, send_from_directory, render_template_string
import os
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 双目录配置
UPLOAD_DEL_DIR = "./uploads"   # 可上传、可删除
READONLY_DIR = "./readonlys"   # 只读、不可删、不可上传

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar', 'py', 'json', 'md', 'exe', 'tar.gz', '7z'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 1GB

os.makedirs(UPLOAD_DEL_DIR, exist_ok=True)
os.makedirs(READONLY_DIR, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_size(byte_num):
    if byte_num < 1024:
        return f"{byte_num} B"
    elif byte_num < 1024 ** 2:
        return f"{round(byte_num/1024, 2)} KB"
    elif byte_num < 1024 ** 3:
        return f"{round(byte_num/(1024**2), 2)} MB"
    else:
        return f"{round(byte_num/(1024**3), 2)} GB"

def get_dir_file_list(folder_path):
    res = []
    for f in os.listdir(folder_path):
        fp = os.path.join(folder_path, f)
        if os.path.isfile(fp):
            size = os.path.getsize(fp)
            res.append({"name": f, "size": size, "size_text": format_size(size)})
    return res

def get_dir_total_info(folder_path):
    total_size = 0
    file_list = get_dir_file_list(folder_path)
    for item in file_list:
        total_size += item["size"]
    disk_usage = shutil.disk_usage(folder_path)
    used_percent = round(100 * total_size / disk_usage.total, 2) if disk_usage.total > 0 else 0
    return {
        "file_count": len(file_list),
        "total_size": total_size,
        "used_percent": used_percent,
        "files": file_list
    }

@app.route('/')
def index():
    upload_info = get_dir_total_info(UPLOAD_DEL_DIR)
    readonly_info = get_dir_total_info(READONLY_DIR)

    html = '''
    <head>
        <meta charset="utf-8">
        <!-- ✅ 这就是浏览器标签栏小图标（header 图标） -->
        <link rel="icon" href="/static/atlat.png" type="image/png" sizes="32x32">
        <title>文件服务</title>
    </head>
    <h1>文件服务 & 存储监控</h1>
    <style>
        .box{border:1px solid #eee;padding:10px;margin:10px 0;border-radius:6px;}
        .red{color:red;}
        .lock{color:#666;}
        .size-text{color:#999;margin-left:8px;font-size:0.9em;}
        .progress-box {margin:10px 0; display:none;}
        .progress-bar {
            width:0%; height:8px; background:#4caf50; border-radius:4px; transition:width 0.3s;
        }
    </style>

    <div class="box">
        <h3>📊 存储占用概览</h3>
        <p>可删除区(uploads)：{{upload_info.file_count}} 个文件 | 已用 {{format_size(upload_info.total_size)}} | 磁盘占比 <b>{{upload_info.used_percent}}%</b></p>
        <p>只读保护区(readonly)：{{readonly_info.file_count}} 个文件 | 已用 {{format_size(readonly_info.total_size)}} | 磁盘占比 <b>{{readonly_info.used_percent}}%</b></p>
    </div>

    <hr>
    <h3>📤 上传文件（可删除分区）</h3>

    <form id="uploadForm" enctype="multipart/form-data">
        <input type="file" name="file" id="file" required>
        <button type="submit">上传</button>
    </form>

    <!-- 进度条 -->
    <div class="progress-box" id="progressBox">
        <div class="progress-bar" id="progressBar"></div>
        <p id="progressText">0%</p>
    </div>

    <hr>
    <h3>✅ 可删除文件区</h3>
    <ul>
    {% for item in upload_info.files %}
        <li>
            <a href="/download/upload/{{item.name}}" target="_blank">{{item.name}}</a>
            <span class="size-text">{{item.size_text}}</span>
            <a href="/delete/{{item.name}}" class="red" onclick="return confirm('确定删除？')">删除</a>
        </li>
    {% endfor %}
    </ul>

    <hr>
    <h3>🔒 只读禁止删除区</h3>
    <ul class="lock">
    {% for item in readonly_info.files %}
        <li>
            <a href="/download/readonly/{{item.name}}" target="_blank">{{item.name}}</a>
            <span class="size-text">{{item.size_text}}</span>
        </li>
    {% endfor %}
    </ul>

    <script>
        const form = document.getElementById('uploadForm');
        const progressBox = document.getElementById('progressBox');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(form);
            const xhr = new XMLHttpRequest();

            xhr.open('POST', '/upload');

            // 上传进度
            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    progressBar.style.width = percent + '%';
                    progressText.textContent = Math.round(percent) + '%';
                    progressBox.style.display = 'block';
                }
            });

            xhr.onload = function() {
                if (xhr.status === 200) {
                    progressText.textContent = "上传完成！";
                    setTimeout(() => { location.reload(); }, 1000);
                } else {
                    progressText.textContent = "上传失败！";
                }
            };

            xhr.send(formData);
        });
    </script>
    '''

    return render_template_string(
        html,
        upload_info=upload_info,
        readonly_info=readonly_info,
        format_size=format_size
    )

# 上传接口
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "未选择文件"
    file = request.files['file']
    if file.filename == '':
        return "文件名为空"
    if file:
        filename = file.filename
        if "\\" in filename or "/" in filename:
            filename = secure_filename(filename)
        file.save(os.path.join(UPLOAD_DEL_DIR, filename))
        return "ok"
    return "不支持的文件类型"

# 删除
@app.route('/delete/<filename>')
def delete_file(filename):
    if "\\" in filename or "/" in filename:
        filename = secure_filename(filename)
    path = os.path.join(UPLOAD_DEL_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return "<a href='/'>返回</a>"

# 下载
@app.route('/download/upload/<filename>', methods=['GET', 'HEAD'])
def download_upload(filename):
    return send_from_directory(UPLOAD_DEL_DIR, filename, as_attachment=True)

@app.route('/download/readonly/<filename>', methods=['GET', 'HEAD'])
def download_static(filename):
    return send_from_directory(READONLY_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    # nohup python3 -u file_server.py > log_file.log 2>&1 &
    # 需要/static/x.png
    app.run(host='127.0.0.1', port=9090, debug=True)