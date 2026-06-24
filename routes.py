from flask import render_template, url_for, request, redirect, send_from_directory,session,jsonify,flash
from markupsafe import escape
from models import Student,Task,Project,Supervisor,Notification,Supervisor_notification,Meeting,Message,Discussion
from werkzeug.utils import secure_filename
import os
import requests
from datetime import datetime,time, date
from graduation_similarity_system import EmbeddingModel, SimilaritySystem, build_project_text
import pandas as pd
import json

domain = 'http://127.0.0.1:5001'
MINTEAMSIZE = 2
MAXTEAMSIZE = 5
MAXPROJECTSPERSUPERVISOR = 3
COMPARISONYEARS = 3 
DOCUMENTATIONDEADLINE = '2024-06-15'  # Format: YYYY-MM-DD
IDEASDEADLINE = '2024-05-01'
RESULTSANNOUNCEMENTDATE = '2026-06-22' 

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model

def register_routes(app,db):

    @app.route('/')
    def homepage():
        students = Student.query.all()
        supervisors = Supervisor.query.all()
        projects = Project.query.all() 
        return render_template('homepage.html',students=students,projects=projects,supervisors=supervisors)

    @app.route("/home")
    def home():
        if 'logged' in session.keys(): 
            name = session["name"]
            if session['project_id'] : 
                project = Project.query.get_or_404(session['project_id'])
            return render_template("home.html",data=session,project=project if session['project_id'] else "")
        return render_template("homepage.html")

    @app.route('/logout')
    def logout():
        session.clear()
        # session['logged'] = False
        return redirect('/')
        
    @app.route("/account/<string:id>")
    def account(id):
        if 'logged' in session.keys(): 
            if id == 'me' or id == session['public_id']:
                name = session['name']
                specialty = session['specialty']
                department = session['department']
                image = session['image'] if 'image' in session.keys() else '/static/uploads/my_photo.jpg'
                phone = session['phone']
                email = session['email']
                linkedin = session['linkedin']
                github = session['github']
                if session['role'] in ['Doctor','Assistant'] :
                    role = session['role']
                    projects = session['projects']
                    return render_template('account.html',specialty=specialty, phone=phone, name=name, email=email, department=department, projects=projects, role=role, image=image,linkedin=linkedin,github=github,data=session)
                else : 
                    year = session['year']
                    in_team = session['in_team']
                    project_id = session['project_id']
                    skills = session['skills']
                    return render_template('account.html',skills=skills,specialty=specialty, phone=phone, name=name, email=email, year=year, department=department, project_id=project_id, in_team=in_team,linkedin=linkedin,github=github, image=image,data=session) 
            else :
                if id.startswith('d') or id.startswith('a') : 
                    id = int(id[1:])
                    supervisor = Supervisor.query.get_or_404(id)
                    return render_template('account.html',supervisor=supervisor,data=session)
                else:
                    id = int(id[1:])
                    student = Student.query.get_or_404(id)
                    return render_template('account.html',student=student,data=session)
        else :
            return redirect('/sign-in')
    @app.route('/edit/user/data', methods=['POST','GET'])
    def edit_user_data():
        if 'logged' not in session:
            return redirect('/sign-in')

        student = Student.query.get_or_404(session['pid'])

        if request.method == 'GET':
            name = student.name
            phone = student.phone or ''
            specialties = student.specialties or ''
            year = student.year or ''
            password = '' 
            # skills stored as list -> convert to comma string for JS
            skills = ','.join(student.get_skills()) if student.get_skills() else ''
            linkedin = student.linkedin_url or ''
            github = student.github_url or ''
            profile_image = student.image or '' 

            return render_template('edit_info.html',
                                name=name, phone=phone, year=year,
                                password=password, specialties=specialties,
                                skills=skills, linkedin=linkedin, github=github,
                                profile_image=profile_image)


        name = request.form.get('name')
        phone = request.form.get('phone')
        year = request.form.get('year')
        specialties = request.form.get('specialties')
        linkedin = request.form.get('linkedin')
        github = request.form.get('github')
        password = request.form.get('password')
        

        skills_str = request.form.get('skills', '')
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]

        student.name = name
        student.phone = phone
        student.specialties = specialties
        student.year = year
        student.linkedin_url = linkedin
        student.github_url = github
        if password: 
            student.password = password
        student.set_skills(skills_list) 

        # 2. Profile picture upload
        file = request.files.get('profile_picture')
        if file and file.filename != '':
            if allowed_file(file.filename):
                original = secure_filename(file.filename)
                unique_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(file_path)
                student.image = f"/static/uploads/{unique_name}"
                session['image'] = student.image
            else:
                flash('Image format not allowed (use PNG, JPG, JPEG, GIF)', 'error')
                return redirect(request.url)

        db.session.commit()

        # Update session values to keep them consistent
        session['name'] = student.name
        session['specialty'] = student.specialties
        session['phone'] = student.phone
        session['year'] = student.year
        session['password'] = student.password  # be careful with plain text
        session['skills'] = skills_list
        session['linkedin'] = student.linkedin_url
        session['github'] = student.github_url
        session['image'] = student.image

        return redirect('/account/me')

    @app.route('/sign-up', methods=['POST','GET'])
    def sign_up():
        if request.method == 'GET' : 
            return render_template('sign_up.html')
        elif request.method == 'POST':
            name = request.form.get('name')
            phone = request.form.get('phone')
            email = request.form.get('email')
            specialties = request.form.get('specialty')
            year = request.form.get('year')
            skills = request.form.get('skills')
            department = request.form.get('department')
            linkedin = request.form.get('linkedin')
            github = request.form.get('github')
            skills = request.form.get('skills') if request.form.get('skills') else []
            password = request.form.get('password')
            if Student.query.filter_by(email=email).count()> 0 :
                    flash("email already exist!","error")
                    return render_template('sign_up.html')
            else :
                student = Student(name=name,specialties=specialties, phone=phone, email=email, department=department, year=year,skills=skills, linkedin_url=linkedin,github_url=github,password=password)
                student.set_skills(skills)
                db.session.add(student)
                db.session.commit()

            return redirect('/sign-in')

    @app.route('/sign-in', methods=['POST','GET'])
    def sign_in():
        if request.method == 'POST': 
            email = request.form['email']
            password = request.form['password']

            if Student.query.filter_by(email=email).count() > 0 :
                student = Student.query.filter_by(email=email).first()
                if student and student.password == password :
                    session['pid'] = student.pid
                    session['name'] = student.name
                    session['specialty'] = student.specialties
                    session['phone'] = student.phone
                    session['email'] = student.email
                    session['year'] = student.year
                    session['department'] = student.department
                    session['image'] = student.image
                    session['password'] = student.password
                    session['logged'] = True
                    session['project_id'] = student.project_id
                    session['in_team'] = student.in_team
                    session['role'] = 'Student'
                    session['public_id'] = student.public_id
                    session['skills'] = student.get_skills()
                    session['linkedin'] = student.linkedin_url,
                    session['github'] = student.github_url 
                    return redirect('/home')
                else :
                    flash("Wrong email or password!","error")
                    return render_template('sign_in.html')
            else :
                    flash("Wrong email or password!","error")
                    return render_template('sign_in.html')
        elif request.method == 'GET':
            return render_template('sign_in.html')

    # ------------ uploading files -----------------
    ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif','pdf'} 
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.',1)[1] in ALLOWED_EXTENSIONS

    @app.route('/upload/<string:_type>', methods=['GET','POST']) # implement full protection and consider error handling
    def upload_file(_type):
        if 'logged' in session.keys() :
            if request.method == 'GET':
                return render_template('upload_file.html')
            elif request.method == 'POST':
                file = request.files['file']
                if allowed_file(file.filename):
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'],secure_filename(file.filename)))
                    if _type == "image" : 
                        img = Student.query.get_or_404(session['pid'])
                        img.image = f"/static/uploads/{file.filename}"
                        db.session.commit()
                        session['image'] = f"/static/uploads/{file.filename}"
                        return redirect('/account/me')
                    elif _type == "attachment": 
                        my_project = Project.query.get_or_404(session['project_id'])
                        attachments = my_project.get_attachment()
                        attachments.append(f"/static/uploads/{file.filename}")
                        my_project.set_attachments(attachments)
                        db.session.commit()
                        return redirect(f'/project/{session["project_id"]}')
                else :
                    flash('Extension Is Not Allowed!','error')
                    return render_template('upload_file.html')
        else:
            return redirect('/sign-in')

    @app.route('/remove_attachment',methods=['POST'])
    def remove_attachment():
        file_path = request.form.get('file_path')
        full_file_path = app.config['PROJECT_DIR']+file_path
        if os.path.exists(full_file_path) : 
            os.remove(full_file_path)
            my_project = Project.query.get_or_404(session['project_id'])
            attachments = my_project.get_attachment()
            if file_path in attachments :
                attachments.remove(file_path)
                my_project.set_attachments(attachments)
                db.session.commit()
                return redirect(f'/project/{session["project_id"]}')
            else : 
                flash(f'{file_path} does not exist!')
                return redirect(f'/project/{session["project_id"]}')
        else : 
            flash(f'{file_path} does not exist!')
            return redirect(f'/project/{session["project_id"]}')

        
    @app.route('/todo',methods=['GET','POST'])
    def todo():
        if 'logged' in session.keys() : 
            if request.method == 'GET':
                if 'project_id' in request.args: # add check after this if it is a supervisor and this project is his
                    project_members = Project.query.get_or_404(request.args['project_id']).members
                    return render_template('tasks.html',members = project_members,data=session)
                else:
                    if session['role'] == 'Student':
                        if session['in_team']:
                            student = Student.query.get(session['pid'])
                            return render_template('tasks.html',student = student,data=session)
                        else : 
                            flash("Can't access task page if you're not in team!","error")
                            return redirect('/ideas')
                    flash("You're not a student!","error")
                    return redirect('/my_projects')
            elif request.method == 'POST':
                task = request.form.get('task')
                date = request.form.get('deadline')
                assigned_to = request.form.get('assigned')
                if not date: 
                    flash("Please add a deadline!","error")
                    if 'project_id' in request.args:
                        return redirect(f'/todo?project_id={request.args["project_id"]}')
                    else:
                        return redirect('/todo')
                if session['role'] != 'Student' and not assigned_to:
                    flash("Please choose which student to assign task to!","error")
                    if 'project_id' in request.args:
                        return redirect(f'/todo?project_id={request.args["project_id"]}')
                    else:
                        return redirect('/todo')
                deadline = datetime.strptime(date,"%Y-%m-%d").date() # converts html form date to python date object
                t = Task(description=task,student_id=assigned_to if assigned_to else session['pid'],deadline=deadline) # add project_id
                db.session.add(t)
                db.session.commit()
                if 'project_id' in request.args:
                    return redirect(f'/todo?project_id={request.args["project_id"]}')
                else:
                    return redirect('/todo')
        else:
                return redirect('/sign-in')

    @app.route('/team_tasks/<int:pid>')
    def team_tasks(pid):
        project_members = Project.query.get_or_404(pid).members
        # for member in project_members:
        return render_template('tasks.html',members=project_members)

    @app.route('/change_status/<tid>',methods=['POST'])
    def change_status(tid):
        if 'logged' in session.keys() :
            task = Task.query.get(tid)
            task.status = "Done"
            db.session.commit()
            source = request.form.get('source')
            return redirect(source)
        else:
            return redirect('/sign-in')

    @app.route('/delete/task/<int:id>',methods=['POST'])
    def delete_task(id):
        if 'logged' in session.keys() :
            t = Task.query.get_or_404(id)
            db.session.delete(t)
            db.session.commit()
            source = request.form.get('source')
            return redirect(source)
        else:
            return redirect('/sign-in')

    @app.route('/friends') # AI Edited
    def friends():
        if 'logged' not in session:
            return redirect('/sign-in')

        specialty_filter = request.args.get('specialty', '').strip()
        not_in_team_only = request.args.get('not_in_team', '0') == '1'
        
        query = Student.query
        
        if specialty_filter:
            query = query.filter(Student.specialties == specialty_filter)
        
        if not_in_team_only:
            query = query.filter(Student.in_team == False)
        
        friends_list = query.all()
        
        # Get all distinct specialties for the dropdown ((( NEED TO UNDERSTAND THIS ONE BETTER)))
        specialties = db.session.query(Student.specialties).distinct().all()
        specialties = sorted([s[0] for s in specialties if s[0]])
        
        return render_template('friends.html',users=friends_list,in_team=session['in_team'],my_id=session['pid'],specialties=specialties,current_specialty=specialty_filter,not_in_team_checked=not_in_team_only,this_year=datetime.now().year)

    @app.route('/req_to_add/<int:id>',methods=['POST'])
    def req_to_add(id):
        if Notification.query.filter_by(action='add',_from_id=session['pid'],_from_name=session['name'],student_id=id,project_id=session['project_id']).count()< 1:
            new_notification = Notification(action='add',_from_id=session['pid'],_from_name=session['name'],student_id=id,project_id=session['project_id'])
            db.session.add(new_notification)
            db.session.commit()
            flash("Request sent!","info")
        else : 
            flash("Request already sent!","info")
        return redirect('/friends')
    @app.route('/add_to_team/<int:nid>/<int:id>/<string:action>',methods=['POST'])
    def add_to_team(nid, id, action): # accepting team leader req to join his team
        if action == 'accept' : 
            new_member = Student.query.get_or_404(session['pid'])
            project_id = Student.query.get_or_404(id).project_id
            project = Project.query.get_or_404(project_id)
            members = project.get_members() 
            if len(members) < 6 : 
                members.append(session['pid'])
                project.set_members(members)
                new_member.in_team = True
                new_member.project_id = project_id
                session['project_id'] = project_id
                session['in_team'] = True
                if len(members) == project.intended_team_size : 
                    project.status = "TeamComplete"
            else :
                flash('Team is full!','error')
        deleted_notification = Notification.query.get_or_404(nid) 
        db.session.delete(deleted_notification)
        db.session.commit()
        if action == 'accept' :
            return redirect(f'/project/{session['project_id']}')
        else : 
            return redirect(f'/notifications')


    @app.route('/join/<int:id>',methods=['GET']) # req to join a team
    def join(id):
        if 'logged' in session.keys():
            project = Project.query.get(id)
            if Notification.query.filter_by(action='join',_from_id=session['pid'],_from_name=session['name'],student_id=project.leader).count()<1:
                notification = Notification(action='join',_from_id=session['pid'],_from_name=session['name'],student_id=project.leader)
                db.session.add(notification)
                db.session.commit()
                flash("Request sent!","info")
            else :
                flash("Request already sent","info")
            return redirect('/ideas')
        else:
            return redirect('/sign-in')
            
    @app.route('/resp_join_req/<int:nid>/<int:from_id>/<string:action>',methods=['POST']) # team leader accepted join req
    def resp_join_req(nid, from_id, action):
        if action == 'accept':
            project = Project.query.get_or_404(session['project_id'])
            members = project.get_members()
            if len(members) < 6 : 
                members.append(from_id)
                project.set_members(members)

                student = Student.query.get_or_404(from_id)
                student.in_team = True
                student.project_id = session['project_id']
                if len(members) == project.intended_team_size : 
                    project.status = "TeamComplete"
            else :
                flash('Team is full!','error')
        notification = Notification.query.get_or_404(nid)
        db.session.delete(notification)
        db.session.commit()
        return redirect('/notifications')

    @app.route('/delete/user/<int:id>',methods=['POST'])
    def delete_student(id):
        if 'logged' in session.keys() :
            p = Student.query.get_or_404(id)
            db.session.delete(p)
            db.session.commit()
            return redirect('/friends')
        else:
            return redirect('/sign-in')

    @app.route('/new_project',methods=['POST','GET'])
    def new_project():
        if 'logged' in session.keys() :
            if request.method == 'GET':
                if 'action' in request.args:
                    project = Project.query.get_or_404(session['project_id'])
                    return render_template('new_project.html',project=project)
                return render_template('new_project.html')
            else : 
                name = request.form.get('name')
                description = request.form.get('description')
                data = requests.post(f'{domain}/api/check-similarity',json={"project_name":name,"description":description})
                res = data.json() 
                if res['is_similar'] and res['is_similar']==True : 
                    flash(f"Your idea is to similar with this idea(s) :\n {[[p['project'],p['score']] for p in res["similar_projects"]]}","error")
                    return redirect(request.referrer)

                similar_ideas = []
                for project in res["similar_projects"]:
                    if project["score"] > 0.60:
                        similar_ideas.append([project["project"],float(project["score"])*100])

                available_fields = ['AI','Network','Embedded','Web','Cyber Security','Desktop','IT','Mobile']
                fields = []

                for field in available_fields : 
                    if request.form.get(field) :
                        fields.append(field)

                # edit ptoject (only student can edit)
                if 'action' in request.args:
                    p = Project.query.get_or_404(session['project_id'])
                    if p.doctor and p.assistent : 
                        flash("You can't edit this project anymore!","error")
                        return redirect(request.refarrer)
                    p.name =  request.form.get('name')
                    p.description = request.form.get('description')
                    p.set_similar_ideas(similar_ideas)
                    p.set_fields(fields)
                    db.session.commit()

                    flash('Edited successfully!','info')
                    return redirect(f'/project/{session['project_id']}')


                year = datetime.now().year
                if Project.query.filter_by(name=name, description=description).count()>0:
                    flash("Project already exist!","error")
                    return redirect('/new_project')
                project = Project(name=name, description=description, year=year,leader=session['pid'])
                project.set_fields(fields)
                project.set_similar_ideas(similar_ideas)
                db.session.add(project)
                db.session.commit()

                members = []
                members.append(session['pid'])
                project = Project.query.filter_by(description=description).first()
                project.set_members(members)
                project_id = project.pid

                student = Student.query.get_or_404(session['pid'])
                if not student.project_id : 
                    student.project_id = project_id
                    session['project_id'] = project_id
                else :
                    old_project = Project.query.get_or_404(student.project_id)
                    members = old_project.get_members()
                    if len(members) > 1 : 
                        old_project.leader = members[1]
                        members.remove(student.pid)
                        old_project.set_members(members)
                    else :
                        db.session.delete(old_project)
                    student.project_id = project_id
                    session['project_id'] = project_id
                student.in_team = True 
                session['in_team'] = True
                db.session.commit()

                return redirect('/ideas')
        else:
            return redirect('/sign-in')
    
    @app.route('/exit_team',methods=['POST'])
    def exit_team():
        student = Student.query.get_or_404(session['pid'])
        old_project = Project.query.get_or_404(session['project_id'])
        members = old_project.get_members()
        if len(members) > 1 : 
            old_project.leader = members[1]
            members.remove(student.pid)
            old_project.set_members(members)
        else :
            db.session.delete(old_project)
        student.in_team = False
        student.project_id = None
        session['in_team'] = False
        session['project_id'] = None
        db.session.commit()
        return redirect('/projects')
    
    @app.route('/kick/<int:project_id>/<int:student_id>', methods=['POST'])
    def kick_member(project_id, student_id):
        if 'logged' not in session:
            return redirect('/sign-in')
        
        project = Project.query.get_or_404(project_id)
        student = Student.query.get_or_404(student_id)
        
        if session['pid'] != project.leader:
            flash('Only the team leader can remove members.', 'error')
            return redirect(url_for('project_detail', id=project_id))

        if student.pid == project.leader:
            flash('You cannot remove the team leader.', 'error')
            return redirect(url_for('project_detail', id=project_id))
        
        members = project.get_members()
        if student.pid in members:
            members.remove(student.pid)
            project.set_members(members)
        
        student.in_team = False
        student.project_id = None

        session['in_team'] = False
        session['project_id'] = None
        
        db.session.commit()
        flash(f'{student.name} has been removed from the team.', 'success')
        return redirect(url_for('project_detail', id=project_id))

    @app.route('/projects')
    def projects():
            this_year = str(datetime.now().year)
            projects = Project.query.filter(Project.year<this_year)
            if 'field' in request.args and request.args.get('field') != 'all':
                projects = [p for p in projects if request.args.get('field') in p.get_fields()]
            if 'year' in request.args and request.args.get('year') != 'all': 
                projects = projects.filter_by(year = request.args.get('year'))
            if 'featured' in request.args :
                projects = projects.filter_by(special=True)
            return render_template('projects.html',projects=projects,data=session,this_year =this_year)

    @app.route('/ideas')
    def ideas():
        this_year = str(datetime.now().year)
        projects = Project.query.filter_by(year=this_year)
        if 'field' in request.args and request.args.get('field') != 'all':
            projects = [p for p in projects if request.args.get('field') in p.get_fields()]
        if 'featured' in request.args :
            projects = projects.filter_by(special=True)
        return render_template('ideas.html',projects=projects,data=session)

    @app.route('/project/<id>')
    def project_detail(id):
        project = Project.query.get_or_404(id)
        s = Supervisor.query
        doctor = s.get_or_404(project.doctor) if project.doctor else None
        assistant = s.get_or_404(project.assistent) if project.assistent else None 
        messages = Message.query.filter_by(project_id=id)
        show = False
        announcement = datetime.strptime(RESULTSANNOUNCEMENTDATE, '%Y-%m-%d').date()
        if announcement >= date.today() :
            show = True
        return render_template(
            'project_details.html',
            data=session if session else "", 
            project=project,
            fields=project.get_fields(),
            attachments = project.get_attachment(),
            doctor=doctor,
            assistant=assistant,
            messages=messages,show=show)

    @app.route('/supervisor_register_0x1F', methods=['GET', 'POST'])
    def supervisor_signup():
        if request.method == 'POST':
            name = request.form.get('name')
            phone = request.form.get('phone')
            email = request.form.get('email')
            password = request.form.get('password')
            specialty = request.form.get('specialty')
            role = request.form.get('role')
            department = request.form.get('department')
            linkedin = request.form.get('linkedin')
            github = request.form.get('github')

            if not all([name, phone, email, password, role]):
                flash('Name, Phone, Email, Password, and Role are required.', 'error')
                return redirect(url_for('supervisor_signup'))

            if role not in ['Doctor', 'Assistant']:
                flash('Role must be either "Doctor" or "Assistant".', 'error')
                return redirect(url_for('supervisor_signup'))

            existing = Supervisor.query.filter((Supervisor.email == email) | (Supervisor.phone == phone)).first()
            if existing:
                flash('A supervisor with that email or phone already exists.', 'error')
                return redirect(url_for('supervisor_signup'))

            #hashed_pw = generate_password_hash(password)
            new_supervisor = Supervisor(name=name,phone=phone,email=email,password=password,specialty=specialty,role=role,github_url=github,linkedin_url=linkedin,department=department)
            db.session.add(new_supervisor)
            db.session.commit()

            flash('Supervisor account created successfully. Please log in.', 'success')
            return redirect(url_for('supervisor_signin')) 

        return render_template('supervisor_signup.html')
    @app.route('/supervisor_signin', methods=['POST','GET'])
    def supervisor_signin():
        if request.method == 'POST': 
            email = request.form['email']
            password = request.form['password']
            if Supervisor.query.filter_by(email=email).count() > 0:
                supervisor = Supervisor.query.filter_by(email=email).first()
                if supervisor and supervisor.password == password :
                    session['sid'] = supervisor.sid
                    session['name'] = supervisor.name
                    session['specialty'] = supervisor.specialty
                    session['phone'] = supervisor.phone
                    session['email'] = supervisor.email
                    session['department'] = supervisor.department
                    session['password'] = supervisor.password
                    session['image'] = supervisor.image
                    session['linkedin'] = supervisor.linkedin_url
                    session['github'] = supervisor.github_url
                    session['logged'] = True
                    session['role'] = supervisor.role
                    session['projects'] = [project.pid for project in supervisor.projects]
                    session['number_of_projects'] = supervisor.projects_limit or 10
                    session['public_id'] = supervisor.public_id
                    return redirect('/supervisor_dashboard')
                else :
                    flash("Wrong email or password!","error")
                    return render_template('supervisor_signin.html')
            else :
                flash("Wrong email or password!","error")
                return render_template('supervisor_signin.html')
        elif request.method == 'GET':
            return render_template('supervisor_signin.html')

    @app.route('/supervisor_dashboard',methods=['GET'])
    def supervisor_dashboard():
        if 'logged' in session.keys(): 
            return render_template('supervisor_dashboard.html',data=session)
        return render_template('supervisor_signin.html')
    @app.route('/supervisors') # make the supervisors list only from same department 
    def supervisors():
        if 'logged' in session.keys():
            if session['in_team'] == True:
                supervisors = Supervisor.query.all()
                my_project = Project.query.get_or_404(session['project_id'])
                return render_template('supervisors.html',supervisors=supervisors,my_id=session['pid'],my_project=my_project)
            else :
                flash('Join team to register with a supervisor!',"error")
                return redirect('/home')
        else:
            return redirect('/sign-in')

    @app.route('/req_to_supervise/<int:_from_id>/<int:sid>',methods=['POST'])
    def req_to_supervise(sid,_from_id):
        student = Student.query.get_or_404(_from_id)
        if Supervisor_notification.query.filter_by(_from_id=_from_id,action='supervise',_from_name=student.name,supervisor_id=sid,project_id=student.project_id).count()<1:
            new_notification = Supervisor_notification(_from_id=_from_id,action='supervise',_from_name=student.name,supervisor_id=sid,project_id=student.project_id)
            db.session.add(new_notification)
            project = Project.query.get_or_404(student.project_id)
            project.under_review = True
            project.status = "UnderReview"
            db.session.commit()

            flash('Request sent successfully!','success')
        else : 
            flash('Request already sent!','error')
        return redirect(url_for('supervisors'))

    @app.route('/res_to_supervision/<int:nid>/<int:_from_id>/<string:action>',methods=['POST'])
    def res_to_supervision(nid,action,_from_id):
        project_id = Student.query.get_or_404(_from_id).project_id
        project = Project.query.get_or_404(project_id)
        if action== 'accept':
            project.status = "Approved"
            doctor,assistant = False,False
            for supervisor in project.supervisors : 
                if supervisor.role == 'Doctor': 
                    doctor =True
                else : 
                    assistant = True
            if session['role'] == 'Doctor' and doctor==False:
                project.doctor = session['sid']
            elif session['role'] == 'Assistant' and assistant==False:
                project.assistent = session['sid']
            else :
                flash(f"Team already has a {session['role']}","error")
                n = Supervisor_notification.query.get_or_404(nid)
                db.session.delete(n)
                db.session.commit()
                return redirect('/notifications')

            other_request =  Supervisor_notification.query.filter_by(project_id=project_id,supervisor_id=session['sid']).filter_by(nid!=nid).all()
            db.session.delete(other_request)
            Supervisor.query.get_or_404(session['sid']).projects.append(project)
        else :
            project.status = "Rejected"
        n = Supervisor_notification.query.get_or_404(nid)
        db.session.delete(n)
        feedback = request.form.get('feedback')
        if feedback and feedback != "":
            message = Message(content=feedback,direction=2,message_type='feedback',project_id=project_id,supervisor_id=session.get('sid')) 
            db.session.add(message)
        db.session.commit()
        return redirect('/notifications')

    @app.route('/my_projects')
    def my_projects():
        if session['role'] != 'Student':
            projects = Supervisor.query.get_or_404(session['sid']).projects
            return render_template('my_projects.html',projects=projects,current_year=datetime.now().year)
        return redirect('/sign-in')

    @app.route('/meeting',methods=['POST','GET'])
    def meeting():
        if session['role'] != 'Student':
            if 'project_id' in request.args: 
                if Project.query.get_or_404(request.args.get('project_id')).doctor == session['sid']:
                    if request.method == 'GET':
                        return render_template('meeting.html',project_id=request.args.get('project_id'))
                    elif request.method == 'POST': 
                        title = request.form.get('title')
                        notes = request.form.get('notes','').strip() or None
                        if 'online' in request.form:
                            place = 'online'
                        else : 
                            place = 'in_person'

                        meeting_date = request.form.get('date')
                        meeting_time = request.form.get('time')
                        link = request.form.get('link','').strip() or None
                        location = request.form.get('location').strip() or None

                        meeting_date = date.fromisoformat(meeting_date)
                        meeting_time = time.fromisoformat(meeting_time)

                        supervisor = session['sid'] 
                        
                        project_id = request.args.get('project_id')
                        meeting = Meeting(title=title,notes=notes,date=meeting_date,time=meeting_time,place=place,link=link,project_id=project_id,location=location,supervisor_id=supervisor)
                        db.session.add(meeting)
                        db.session.commit()
                        flash("Meeting scheduled successfully!","info")
                        return redirect(f'/project/{request.args.get('project_id')}')
                flash("You're not allowed here!","error")
                return redirect('/supervisor_dashboard')
            flash("Missing project ID parameter!","error")
            return redirect('/supervisor_dashboard')
        flash("You're not allowed here!","error")
        return redirect('/home')

    def delete_old_meetings():
        today = date.today()
        old_meetings = Meeting.query.filter(Meeting.date<today).all()
        for meeting in old_meetings : 
            db.session.delete(meeting)
        db.session.commit()

    @app.route('/my_meetings',methods=['GET'])
    def my_meetings():
        delete_old_meetings()
        meetings = Meeting.query.all()
        return render_template('my_meetings.html', meetings=meetings,data=session)


    @app.route('/edit_projects_number',methods=['POST'])
    def edit_projects_number():
        number = request.form.get('number')
        s = Supervisor.query.get_or_404(session['sid'])
        s.projects_limit = number
        session['number_of_projects'] = number
        db.session.commit()
        return redirect(url_for('supervisor_dashboard'))

    @app.route('/notifications')
    def notifications():
        if 'logged' in session.keys():
            if session['role'] == 'Doctor' or session['role'] == 'Assistant':
                supervisor = Supervisor.query.get_or_404(session['sid'])
                # project = Student.query.get_or_404()
                return render_template('notifications.html',notifications=supervisor.notifications,data=session)
            else :
                student = Student.query.get_or_404(session['pid'])
                return render_template('notifications.html',notifications=student.notifications,data=session)
        else:
            return redirect('/sign-in')

    @app.route('/messages',methods=['POST'])
    def messages():
        # validate if missing data
        if session['role'] == 'Student':
            supervisor = request.form.get('supervisor')
            content = request.form.get('content')
            new_message = Message(direction=1,project_id=session['project_id'],content=content,supervisor_id=supervisor)
            db.session.add(new_message)
            db.session.commit()
        else: 
            project_id = request.form.get('project_id')
            content = request.form.get('content')
            new_message = Message(direction=2,project_id=project_id,content=content,supervisor_id=session['sid'])
            db.session.add(new_message)
            db.session.commit() 
        
        return redirect(request.referrer)

    @app.route('/first-discussion/<int:project_id>',methods=['POST','GET'])
    def first_discussion(project_id):
        project = Project.query.get_or_404(project_id)
        if not 'sid' in session or not project.doctor or session['sid'] != project.doctor :
          flash("You are not a supervisor in this project","error")
          return redirect(f'/project/{project_id}')
        if request.method == 'GET' : 
            return render_template('first_discussion.html',project=project)
        for member in project.members : 
           member.first_discussion_result = request.form.get(f'degree-for-{member.pid}')
        is_special = request.form.get('special') == 'True'
        project.special = is_special
        if request.form.get('feedback1') and request.form.get('feedback1') != '' :
                message1 = Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=request.form.get('feedback1'),message_type='feedback')
                db.session.add(message1)
        if request.form.get('feedback2') and request.form.get('feedback2') != '' :
                message2= Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=request.form.get('feedback2'),message_type='feedback')
                db.session.add(message2)

        discussions = Discussion.query.filter_by(project_id=project_id).all()
        for discussion in discussions :
            db.session.delete(discussion)  
        db.session.commit()
        flash("Saved successfully!","info")
        return redirect(f'/project/{project_id}')
        

    @app.route('/second-discussion/<int:project_id>', methods=['POST', 'GET'])
    def second_discussion(project_id):
        project = Project.query.get_or_404(project_id)

        if 'sid' not in session or not project.doctor or session['sid'] != project.doctor:
            flash("You are not a supervisor in this project", "error")
            return redirect(f'/project/{project_id}')
        if request.method == 'GET':
            return render_template('second_discussion.html', project=project)
        for member in project.members:
            val = request.form.get(f'finel-project-degree-for-{member.pid}')
            member.finel_project_degree = int(val) if val and val.strip() else None

        project.special = (request.form.get('special') == 'True')

        feedback1 = request.form.get('feedback1')
        if feedback1 and feedback1.strip():
            msg1 = Message(
                direction=2,
                supervisor_id=session['sid'],
                project_id=project_id,
                content=feedback1.strip(),
                message_type='feedback'
            )
            db.session.add(msg1)

        feedback2 = request.form.get('feedback2')
        if feedback2 and feedback2.strip():
            msg2 = Message(
                direction=2,
                supervisor_id=session['sid'],
                project_id=project_id,
                content=feedback2.strip(),
                message_type='feedback'
            )
            db.session.add(msg2)
        Discussion.query.filter_by(project_id=project_id).delete()
        db.session.commit()
        flash("Saved successfully!", "info")
        return redirect(f'/project/{project_id}')

    @app.route('/admin-panel', methods=['GET', 'POST'])
    def admin_panel():
        # Declare all global variables at the top
        global MINTEAMSIZE, MAXTEAMSIZE, MAXPROJECTSPERSUPERVISOR
        global COMPARISONYEARS, DOCUMENTATIONDEADLINE, IDEASDEADLINE, RESULTSANNOUNCEMENTDATE

        if request.method == 'GET':
            return render_template('admin_panel.html',
                                min_team_size=MINTEAMSIZE,
                                max_team_size=MAXTEAMSIZE,
                                max_projects_per_supervisor=MAXPROJECTSPERSUPERVISOR,
                                comparison_years=COMPARISONYEARS,
                                documentation_deadline=DOCUMENTATIONDEADLINE,
                                ideas_deadline=IDEASDEADLINE,
                                results_announcement_date=RESULTSANNOUNCEMENTDATE,
                                theme=session.get('theme', 'light'))

        # POST request
        min_team_size = request.form.get('min_team_size')
        max_team_size = request.form.get('max_team_size')
        max_projects_per_supervisor = request.form.get('max_projects_per_supervisor')
        comparison_years = request.form.get('comparison_years')
        documentation_deadline = request.form.get('documentation_deadline')
        ideas_deadline = request.form.get('ideas_deadline')
        results_announcement_date = request.form.get('results_announcement_date')

        # Validate inputs
        if not all([min_team_size, max_team_size, max_projects_per_supervisor,
                    comparison_years, documentation_deadline, ideas_deadline,
                    results_announcement_date]):
            flash('All fields are required', 'error')
            return redirect(url_for('admin_panel'))

        # Convert to appropriate types
        try:
            min_team_size = int(min_team_size)
            max_team_size = int(max_team_size)
            max_projects_per_supervisor = int(max_projects_per_supervisor)
            comparison_years = int(comparison_years)
        except ValueError:
            flash('Invalid numeric values', 'error')
            return redirect(url_for('admin_panel'))

        # Validate team size
        if min_team_size < 1:
            flash('Minimum team size must be at least 1', 'error')
            return redirect(url_for('admin_panel'))
        if max_team_size < min_team_size:
            flash('Maximum team size cannot be less than minimum team size', 'error')
            return redirect(url_for('admin_panel'))
        if max_team_size > 10:
            flash('Maximum team size cannot exceed 10', 'error')
            return redirect(url_for('admin_panel'))

        # Validate supervisor projects
        if max_projects_per_supervisor < 1:
            flash('Maximum projects per supervisor must be at least 1', 'error')
            return redirect(url_for('admin_panel'))
        if max_projects_per_supervisor > 20:
            flash('Maximum projects per supervisor cannot exceed 20', 'error')
            return redirect(url_for('admin_panel'))

        # Validate comparison years
        if comparison_years < 0:
            flash('Comparison years cannot be negative', 'error')
            return redirect(url_for('admin_panel'))
        if comparison_years > 10:
            flash('Comparison years cannot exceed 10', 'error')
            return redirect(url_for('admin_panel'))

        # Validate dates
        from datetime import datetime
        today = datetime.now().date()

        doc_deadline = datetime.strptime(documentation_deadline, '%Y-%m-%d').date()
        if doc_deadline < today:
            flash('Documentation deadline cannot be in the past', 'error')
            return redirect(url_for('admin_panel'))

        ideas_deadline_date = datetime.strptime(ideas_deadline, '%Y-%m-%d').date()
        if ideas_deadline_date < today:
            flash('Ideas deadline cannot be in the past', 'error')
            return redirect(url_for('admin_panel'))

        results_date = datetime.strptime(results_announcement_date, '%Y-%m-%d').date()
        if results_date < today:
            flash('Results announcement date cannot be in the past', 'error')
            return redirect(url_for('admin_panel'))

        # Update global variables
        MINTEAMSIZE = min_team_size
        MAXTEAMSIZE = max_team_size
        MAXPROJECTSPERSUPERVISOR = max_projects_per_supervisor
        COMPARISONYEARS = comparison_years
        DOCUMENTATIONDEADLINE = documentation_deadline
        IDEASDEADLINE = ideas_deadline
        RESULTSANNOUNCEMENTDATE = results_announcement_date

        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin_panel'))

    @app.route('/new-discussion',methods=['POST','GET'])
    def new_discussion():
        if request.method == 'GET':
          projects = Project.query.all()
          supervisors = Supervisor.query.all()
          return render_template('new_discussion.html',projects=projects,supervisors=supervisors)
        discussion_date = request.form.get('date')
        discussion_time = request.form.get('time')
        location = request.form.get('location').strip() or None

        discussion_date = date.fromisoformat(discussion_date)
        discussion_time = time.fromisoformat(discussion_time)
        supervisors = request.form.get('supervisors')
        project_id = request.form.get('project')
        number = request.form.get('number')
        discussion = Discussion(number=number,project_id=project_id,time=discussion_time,date=discussion_date,location=location)
        db.session.add(discussion)
        db.session.commit()
        discussion = Discussion.query.filter_by(number=number,project_id=project_id,time=discussion_time,date=discussion_date,location=location).first()
        supervisors_list = [int(s) for s in supervisors.split(',')]
        discussion.set_supervisors(supervisors_list)
        content = f"The next discussion for this project will be in {discussion_date} {discussion_time} in {location}"
        message =  Message(direction=2,project_id=project_id,content=content,supervisor_id=session['sid'],message_type='feedback')
        db.session.add(message)
        db.session.commit()
        flash("Created successfully!","info")
        return redirect('/discussions')    
    
    @app.route('/discussions', methods=['GET'])
    def view_discussions():
        # Get all discussions ordered by date and time (newest first)
        discussions = Discussion.query.order_by(
            Discussion.date.asc(), 
            Discussion.time.asc()
        ).all()
        
        # For each discussion, get the supervisor names
        for discussion in discussions:
            supervisor_ids = discussion.get_supervisors()
            supervisor_names = []
            if supervisor_ids:
                for sid in supervisor_ids:
                    supervisor = Supervisor.query.get(sid)
                    if supervisor:
                        supervisor_names.append(supervisor.name)
            discussion.supervisor_names = ', '.join(supervisor_names)
            
            # Get project name
            project = Project.query.get(discussion.project_id)
            discussion.project_name = project.name if project else "Unknown Project"
        today = date.today()
        return render_template('discussions.html', 
                            discussions=discussions,today=today,
                            theme=session.get('theme', 'light'))

    @app.route('/announecments',methods=['POST','GET'])
    def announecments():
        return 'coming soon'

    @app.route('/guide',methods=['POST','GET'])
    def guide():
        return 'coming soon'
                    
    # ========== API V2 ROUTES ==========

    # Generic response helpers
    def api_unauthorized():
        return jsonify({"error": "Authentication required"}), 401

    def api_not_found(resource):
        return jsonify({"error": f"{resource} not found"}), 404

    def api_bad_request(message):
        return jsonify({"error": message}), 400

    # ----------------------------------------------------------------------
    # Public endpoints (no login required)
    @app.route('/api/v2/public/homepage', methods=['GET'])
    def api_public_homepage():
        """Return list of students, supervisors, projects (public)"""
        students = Student.query.all()
        supervisors = Supervisor.query.all()
        projects = Project.query.all()
        return jsonify({
            "students": [{"pid": s.pid, "name": s.name, "email": s.email} for s in students],
            "supervisors": [{"sid": sup.sid, "name": sup.name, "role": sup.role} for sup in supervisors],
            "projects": [{"pid": p.pid, "name": p.name, "year": p.year} for p in projects]
        })

    # ----------------------------------------------------------------------
    # Authentication endpoints (JSON versions of sign-in/sign-up)
    @app.route('/api/v2/sign-up', methods=['POST'])
    def api_sign_up():
        """Register a new student (JSON body)"""
        data = request.get_json()
        if not data:
            return api_bad_request("Missing JSON body")
        name = data.get('name')
        phone = data.get('phone')
        email = data.get('email')
        specialties = data.get('specialties')
        skills = data.get('skills')
        year = data.get('year')
        department = data.get('department')
        password = data.get('password')
        if not all([name, phone, email, year, department, password]):
            return api_bad_request("Missing required fields: name, phone, email, year, department, password")
        if Student.query.filter_by(email=email).count() > 0:
            return jsonify({"error": "Email already exists"}), 400
        student = Student(name=name, specialties=specialties, phone=phone, email=email,
                        department=department, year=year,status="No Idea", password=password)
        student.set_skills(skills)
        db.session.add(student)
        db.session.commit()
        return jsonify({"message": "Student created successfully", "pid": student.pid}), 201

    @app.route('/api/v2/sign-in', methods=['POST'])
    def api_sign_in():
        """Student login, returns session data"""
        data = request.get_json()
        if not data:
            return api_bad_request("Missing JSON body")
        email = data.get('email')
        password = data.get('password')
        student = Student.query.filter_by(email=email).first()
        if not student or student.password != password:
            return jsonify({"error": "Invalid email or password"}), 401
        # Set session (same as web)
        session['pid'] = student.pid
        session['name'] = student.name
        session['specialty'] = student.specialties
        session['skills'] = student.get_skills()
        session['phone'] = student.phone
        session['email'] = student.email
        session['year'] = student.year
        session['department'] = student.department
        session['image'] = student.image
        session['logged'] = True
        session['project_id'] = student.project_id
        session['in_team'] = student.in_team
        session['role'] = 'Student'
        session['public_id'] = student.public_id
        session['status'] = student.status
        return jsonify({
            "message": "Login successful",
            "pid": student.pid,
            "name": student.name,
            "email": student.email,
            "role": "Student",
            "in_team": student.in_team,
            "project_id": student.project_id,
            "skills":student.get_skills(),
            "status" : session['status']
        })

    # Supervisor sign-in
    @app.route('/api/v2/supervisor/sign-in', methods=['POST'])
    def api_supervisor_sign_in():
        data = request.get_json()
        if not data:
            return api_bad_request("Missing JSON body")
        email = data.get('email')
        password = data.get('password')
        sup = Supervisor.query.filter_by(email=email).first()
        if not sup or sup.password != password:
            return jsonify({"error": "Invalid email or password"}), 401
        session['sid'] = sup.sid
        session['name'] = sup.name
        session['specialty'] = sup.specialty
        session['phone'] = sup.phone
        session['email'] = sup.email
        session['department'] = sup.department
        session['image'] = sup.image
        session['logged'] = True
        if email == "admin@system.com" : 
            role = ['Admin']
        else :
            session['role'] = sup.role
        session['projects'] = [p.pid for p in sup.projects]
        session['number_of_projects'] = sup.projects_limit or 10
        session['public_id'] = sup.public_id
        return jsonify({
            "message": "Login successful",
            "sid": sup.sid,
            "name": sup.name,
            "role": sup.role
        })

    @app.route('/api/v2/logout', methods=['POST'])
    def api_logout():
        session.clear()
        return jsonify({"message": "Logged out"})

    # ----------------------------------------------------------------------
    # Account & profile (student & supervisor)
    @app.route('/api/v2/account/me', methods=['GET'])
    def api_account_me():
        if 'logged' not in session:
            return api_unauthorized()
        role = session.get('role')
        if role == 'Student':
            student = Student.query.get(session['pid'])
            if not student:
                return api_not_found("Student")
            return jsonify({
                "pid": student.pid,
                "name": student.name,
                "email": student.email,
                "phone": student.phone,
                "specialties": student.specialties,
                "skills": student.get_skills(),
                "year": student.year,
                "department": student.department,
                "image": student.image,
                "in_team": student.in_team,
                "project_id": student.project_id,
                "linkedin_url": student.linkedin_url,
                "github_url": student.github_url
            })
        elif role in ('Doctor', 'Assistant'):
            sup = Supervisor.query.get(session['sid'])
            if not sup:
                return api_not_found("Supervisor")
            return jsonify({
                "sid": sup.sid,
                "name": sup.name,
                "email": sup.email,
                "phone": sup.phone,
                "specialty": sup.specialty,
                "department": sup.department,
                "image": sup.image,
                "role": sup.role,
                "projects_limit": sup.projects_limit,
                "linkedin_url": sup.linkedin_url,
                "github_url": sup.github_url
            })
        return api_bad_request("Unknown role")

    @app.route('/api/v2/account/<string:public_id>', methods=['GET'])
    def api_account_public(public_id):
        """Get public profile by public_id (e.g., s1, d2, a3)"""
        if public_id.startswith('s'):
            pid = int(public_id[1:])
            student = Student.query.get(pid)
            if not student:
                return api_not_found("Student")
            return jsonify({
                "pid": student.pid,
                "name": student.name,
                "email": student.email,
                "phone": student.phone,
                "specialties": student.specialties,
                "skills":student.get_skills(),
                "year": student.year,
                "department": student.department,
                "image": student.image,
                "in_team": student.in_team,
                "linkedin_url": student.linkedin_url,
                "github_url": student.github_url
            })
        elif public_id.startswith('d') or public_id.startswith('a'):
            sid = int(public_id[1:])
            sup = Supervisor.query.get(sid)
            if not sup:
                return api_not_found("Supervisor")
            return jsonify({
                "sid": sup.sid,
                "name": sup.name,
                "email": sup.email,
                "phone": sup.phone,
                "specialty": sup.specialty,
                "department": sup.department,
                "image": sup.image,
                "role": sup.role
            })
        return api_bad_request("Invalid public ID format")

    @app.route('/api/v2/edit/user/data', methods=['PUT'])
    def api_edit_user_data():
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        data = request.get_json()
        if not data:
            return api_bad_request("Missing JSON")
        student = Student.query.get(session['pid'])
        if not student:
            return api_not_found("Student")
        # Update fields if provided
        if 'name' in data:
            student.name = data['name']
            session['name'] = data['name']
        if 'phone' in data:
            student.phone = data['phone']
            session['phone'] = data['phone']
        if 'specialty' in data:
            student.specialties = data['specialty']
            session['specialty'] = data['specialty']
        if 'skills' in data:
            student.set_skills(data['skills']) 
            session['skills'] = data['skills']
        if 'password' in data:
            student.password = data['password']
            session['password'] = data['password']
        if 'linkedin' in data:
            student.linkedin_url = data['linkedin']
        if 'github' in data:
            student.github_url = data['github']
        db.session.commit()
        return jsonify({
        "message": "Profile updated successfully",
        "user": {
            "pid": student.pid,
            "name": student.name,
            "email": student.email,
            "phone": student.phone,
            "specialty": student.specialties,
            "year": student.year,
            "department": student.department,
            "image": student.image,
            "in_team": student.in_team,
            "project_id": student.project_id,
            "linkedin_url": student.linkedin_url,
            "github_url": student.github_url,
            "skills":student.get_skills()
        } })

    # ----------------------------------------------------------------------
    # Projects (ideas, library, detail, creation, editing)
    @app.route('/api/v2/ideas', methods=['GET'])
    def api_ideas():
        """Current year projects, optional filter by field and featured"""
        this_year = str(datetime.now().year)
        query = Project.query.filter_by(year=this_year)
        field = request.args.get('field')
        featured = request.args.get('featured') == 'true'
        if field and field != 'all':
            # Filtering by field requires checking the JSON field list
            projects = [p for p in query.all() if field in p.get_fields()]
        else:
            projects = query.all()
        if featured:
            projects = [p for p in projects if p.special]
        return jsonify([{
            "pid": p.pid,
            "name": p.name,
            "description": p.description,
            "fields": p.get_fields(),
            "special": p.special,
            "leader": p.leader,
            "status": p.status,
            "members_id":[m.pid for m in p.members],
            "members_name":[m.name for m in p.members],
            "similar_ideas": p.get_similar_ideas() if hasattr(p, 'get_similar_ideas') else [],
            "doctor_id": p.doctor or "no doctor",
            "assistant_id": p.assistent or "no assistant",
            "idea status":p.status or "",
            "Maximum team size": MAXTEAMSIZE
        } for p in projects])

    @app.route('/api/v2/projects', methods=['GET'])
    def api_projects():
        """Past projects (year < current) with filtering"""
        this_year = str(datetime.now().year)
        query = Project.query.filter(Project.year < this_year)
        field = request.args.get('field')
        year = request.args.get('year')
        featured = request.args.get('featured') == 'true'
        if field and field != 'all':
            projects = [p for p in query.all() if field in p.get_fields()]
        else:
            projects = query.all()
        if year and year != 'all':
            projects = [p for p in projects if p.year == year]
        if featured:
            projects = [p for p in projects if p.special]
        return jsonify([{
            "pid": p.pid,
            "name": p.name,
            "description": p.description,
            "year": p.year,
            "fields": p.get_fields(),
            "leader": p.leader,
            "members_id":[m.pid for m in p.members],
            "members_name":[m.name for m in p.members],
            "special": p.special is not None,
            "doctor": p.doctor or "no doctor",
            "assistant": p.assistent or "no assistant"
        } for p in projects])

    @app.route('/api/v2/project/<int:pid>', methods=['GET'])
    def api_project_detail(pid):
        """Full project details including members, supervisors, attachments, messages"""
        project = Project.query.get(pid)
        if not project:
            return api_not_found("Project")
        doctor = Supervisor.query.get(project.doctor) if project.doctor else None
        assistant = Supervisor.query.get(project.assistent) if project.assistent else None
        members = [{"pid": m.pid, "name": m.name} for m in project.members]
        messages = Message.query.filter_by(project_id=pid).all()
        return jsonify({
            "pid": project.pid,
            "name": project.name,
            "description": project.description,
            "year": project.year,
            "fields": project.get_fields(),
            "similar ideas": project.get_similar_ideas(),
            "status": project.status,
            "is_special": project.special or "",
            "leader_id": project.leader,
            "intended team size" :project.intended_team_size,
            "doctor": {
                "sid": doctor.sid,
                "name": doctor.name
            } if doctor else None,
            "assistant": {
                "sid": assistant.sid,
                "name": assistant.name
            } if assistant else None,
            "members": members,
            "attachments": project.get_attachment(),
            "messages": [{
                "mid": m.mid,
                "direction": m.direction,
                "content": m.content,
                "message_type": m.message_type,
                "supervisor_id": m.supervisor_id,
                "timestamp": m.mid  # you may add a timestamp column if needed
            } for m in messages]
        })

    @app.route('/api/v2/new_project', methods=['POST'])
    def api_create_project():
        """Create a new project (student only)"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        data = request.get_json()
        if not data:
            return api_bad_request("Missing JSON")
        name = data.get('name')
        description = data.get('description')
        AI_data = requests.post(f'{domain}/api/check-similarity',json={"project_name":name,"description":description})
        res = AI_data.json() 
        if res['is_similar'] and res['is_similar']==True : 
            return jsonify({"Error": "Your idea is too similar with these idea(s):","similar_projects": [{"project": p['project'],"similarity_score": p['score']} 
        for p in res["similar_projects"]]})

        similar_ideas = []
        for project in res["similar_projects"]:
            if project["score"] > 0.60:
                similar_ideas.append([project["project"],float(project["score"])*100])

        fields = data.get('fields', [])
        if not name or not description:
            return api_bad_request("Name and description required")
        year = datetime.now().year

        intended_team_size = data.get('max_team_size')
        publish_without_team = data.get('publish_without_team')
        selected_members = data.get('selected_members')
        if Project.query.filter_by(name=name, description=description).count()>0:
            return jsonify({"Error":"Project already exist!"})
        project = Project(name=name, description=description, year=year, leader=session['pid'],intended_team_size=intended_team_size,publish_without_team=publish_without_team)
        project.set_fields(fields)
        project.set_similar_ideas(similar_ideas)
        project.set_selected_members(selected_members)
        db.session.add(project)
        db.session.commit()
        # Add creator as first member
        members = [session['pid']]
        project.set_members(members)
        # Update student
        student = Student.query.get(session['pid'])
        if student.project_id:
            # Leave old project
            old_project = Project.query.get(student.project_id)
            if old_project:
                old_members = old_project.get_members()
                if len(old_members) > 1:
                    old_project.leader = old_members[1]
                    old_members.remove(student.pid)
                    old_project.set_members(old_members)
                else:
                    db.session.delete(old_project)
        student.project_id = project.pid
        student.in_team = True
        session['project_id'] = project.pid
        session['in_team'] = True
        res = jsonify({"message": "Project created", "project_id": project.pid,
            "name": project.name,
            "description": project.description,
            "year": project.year,
            "fields": project.get_fields(),            
            "leader": project.leader,
            "members_id":[m.pid for m in project.members],
            "members_name":[m.name for m in project.members],
            "max_team_size" : project.intended_team_size,
            "status":project.status,
            "special": project.special is not None,
            "doctor": project.doctor or "no doctor",
            "assistant": project.assistent or "no assistant",
            "similar_ideas":project.get_similar_ideas()})
        db.session.commit()
        return res , 201

    @app.route('/api/v2/project/<int:pid>', methods=['PUT'])
    def api_edit_project(pid):
        """Edit project (only leader)"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        project = Project.query.get(pid)
        if not project:
            return api_not_found("Project")
        if project.leader != session['pid']:
            return jsonify({"error": "Only team leader can edit project"}), 403
        data = request.get_json()
        if 'name' in data or 'description' in data : 
            name = data['name'] if data['name'] else project.name
            description = data['description'] if data['description'] else project.description

            data = requests.post(f'{domain}/api/check-similarity',json={"project_name":name,"description":description})
            res = data.json() 
            if res['is_similar'] and res['is_similar']==True : 
                return jsonify({"Error": "Your idea is too similar with these idea(s):","similar_projects": [{"project": p['project'],"similarity_score": p['score']} 
            for p in res["similar_projects"]]})

            similar_ideas = []
            for project in res["similar_projects"]:
                if project["score"] > 0.60:
                    similar_ideas.append([project["project"],float(project["score"])*100])
            project.set_similar_ideas(similar_ideas)
            if 'name' in data:
                project.name = data['name']
            if 'description' in data:
                project.description = data['description']
        if 'fields' in data:
            project.set_fields(data['fields'])
        if 'intended_team_size' in data:
            project.intended_team_size = data['intended_team_size']
        db.session.commit()
        return jsonify({"message": "Project updated"})

    # ----------------------------------------------------------------------
    # Team management (join, leave, kick, requests)
    @app.route('/api/v2/join/<int:project_id>', methods=['POST'])
    def api_request_join(project_id):
        """Student requests to join a project"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        project = Project.query.get(project_id)
        if not project:
            return api_not_found("Project")
        if session['in_team']:
            return jsonify({"error": "You are already in a team"}), 400
        # Check duplicate request
        existing = Notification.query.filter_by(action='join', _from_id=session['pid'],
                                                student_id=project.leader, project_id=project_id).first()
        if existing:
            return jsonify({"error": "Request already sent"}), 400
        notif = Notification(action='join', _from_id=session['pid'], _from_name=session['name'],
                            student_id=project.leader, project_id=project_id)
        db.session.add(notif)
        db.session.commit()
        return jsonify({"message": "Join request sent"})

    @app.route('/api/v2/team/requests', methods=['GET'])
    def api_get_team_requests():
        """Get pending join requests for the leader's project"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        project_id = session.get('project_id')
        if not project_id:
            return jsonify({"requests": []})
        project = Project.query.get(project_id)
        if not project or project.leader != session['pid']:
            return jsonify({"error": "Not the team leader"}), 403
        requests = Notification.query.filter_by(action='join', student_id=session['pid']).all()
        return jsonify([{
            "nid": r.nid,
            "from_id": r._from_id,
            "from_name": r._from_name,
            "project_id": r.project_id
        } for r in requests])

    @app.route('/api/v2/team/respond_join/<int:nid>/<string:action>', methods=['POST'])
    def api_respond_join(nid, action):
        """Leader accepts/rejects join request (action = 'accept' or 'reject')"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        notif = Notification.query.get(nid)
        if not notif or notif.action != 'join' or notif.student_id != session['pid']:
            return api_not_found("Request")
        project = Project.query.get(session['project_id'])
        if not project:
            return api_not_found("Project")
        if action == 'accept':
            members = project.get_members()
            if len(members) >= 6:
                return jsonify({"error": "Team is full"}), 400
            members.append(notif._from_id)
            project.set_members(members)
            student = Student.query.get(notif._from_id)
            if student:
                student.in_team = True
                student.project_id = session['project_id']
            db.session.commit()
        db.session.delete(notif)
        db.session.commit()
        return jsonify({"message": f"Request {action}ed"})

    @app.route('/api/v2/exit_team', methods=['POST'])
    def api_exit_team():
        """Current student leaves their team"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        student = Student.query.get(session['pid'])
        if not student.project_id:
            return jsonify({"error": "Not in a team"}), 400
        project = Project.query.get(student.project_id)
        if project:
            members = project.get_members()
            if len(members) > 1:
                if student.pid == project.leader:
                    project.leader = members[1]
                members.remove(student.pid)
                project.set_members(members)
            else:
                db.session.delete(project)
        student.project_id = None
        student.in_team = False
        session['project_id'] = None
        session['in_team'] = False
        db.session.commit()
        return jsonify({"message": "Left team successfully"})

    @app.route('/api/v2/kick/<int:project_id>/<int:student_id>', methods=['POST'])
    def api_kick_member(project_id, student_id):
        """Team leader kicks a member"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        project = Project.query.get(project_id)
        if not project:
            return api_not_found("Project")
        if project.leader != session['pid']:
            return jsonify({"error": "Only leader can kick members"}), 403
        if student_id == project.leader:
            return jsonify({"error": "Cannot kick leader"}), 400
        student = Student.query.get(student_id)
        if not student or student.project_id != project_id:
            return jsonify({"error": "Student not in this team"}), 404
        members = project.get_members()
        if student_id in members:
            members.remove(student_id)
            project.set_members(members)
        student.project_id = None
        student.in_team = False
        db.session.commit()
        return jsonify({"message": "Member kicked"})

    # ----------------------------------------------------------------------
    # Friends (students list with filters)
    @app.route('/api/v2/friends', methods=['GET'])
    def api_friends():
        """List students with optional specialty filter and 'not in team' filter"""
        if 'logged' not in session:
            return api_unauthorized()
        specialty = request.args.get('specialty')
        not_in_team = request.args.get('not_in_team') == 'true'
        query = Student.query
        if specialty:
            query = query.filter(Student.specialties == specialty)
        if not_in_team:
            query = query.filter(Student.in_team == False)
        students = query.all()
        return jsonify([{
            "pid": s.pid,
            "name": s.name,
            "specialties": s.specialties,
            "skills":s.get_skills() if s.get_skills() else [],
            "in_team": s.in_team,
            "year": s.year,
            "department": s.department,
            "image": s.image,
            "status": s.status
        } for s in students])

    @app.route('/api/v2/req_to_add/<int:student_id>', methods=['POST'])
    def api_req_to_add(student_id):
        """Send request to a student to join your team (as leader)"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        if not session.get('in_team') or not session.get('project_id'):
            return jsonify({"error": "You must be in a team to add members"}), 400
        project = Project.query.get(session['project_id'])
        if project.leader != session['pid']:
            return jsonify({"error": "Only leader can send invites"}), 403
        target = Student.query.get(student_id)
        if not target:
            return api_not_found("Student")
        if target.in_team:
            return jsonify({"error": "Student is already in a team"}), 400
        existing = Notification.query.filter_by(action='add', _from_id=session['pid'],student_id=student_id).first()
        if existing:
            return jsonify({"error": "Request already sent"}), 400
        notif = Notification(action='add', _from_id=session['pid'], _from_name=session['name'],
                            student_id=student_id, project_id=session['project_id'])
        db.session.add(notif)
        db.session.commit()
        return jsonify({"message": "Invitation sent"})

    # ----------------------------------------------------------------------
    # Supervisor related (list, request supervision, respond)
    @app.route('/api/v2/supervisors', methods=['GET'])
    def api_supervisors():
        """List all supervisors (optionally filter by department?)"""
        if 'logged' not in session:
            return api_unauthorized()
        supervisors = Supervisor.query.all()
        return jsonify([{
            "sid": s.sid,
            "name": s.name,
            "email": s.email,
            "role": s.role,
            "department": s.department,
            "specialty": s.specialty,
            "projects_limit" : s.projects_limit if s.projects_limit else 10,
            "number_of_projects" : s.projects.count(),
            "image": s.image
        } for s in supervisors])

    @app.route('/api/v2/req_to_supervise/<int:supervisor_id>', methods=['POST'])
    def api_req_to_supervise(supervisor_id):
        """Student requests supervision from a specific supervisor"""
        if 'logged' not in session or session.get('role') != 'Student':
            return api_unauthorized()
        if not session.get('in_team'):
            return jsonify({"error": "You must be in a team to request supervision"}), 400
        sup = Supervisor.query.get(supervisor_id)
        if not sup:
            return api_not_found("Supervisor")
        existing = Supervisor_notification.query.filter_by(_from_id=session['pid'],
                                                        supervisor_id=supervisor_id,
                                                        action='supervise').first()
        if existing:
            return jsonify({"error": "Request already sent"}), 400
        notif = Supervisor_notification(_from_id=session['pid'], action='supervise',
                                        _from_name=session['name'], supervisor_id=supervisor_id,
                                        project_id=session['project_id'])
        project = Project.query.get_or_404(session['project_id'])
        project.under_review = True
        project.status = "UnderReview"
        db.session.add(notif)
        db.session.commit()
        return jsonify({"message": "Supervision request sent"})

    @app.route('/api/v2/supervisor/notifications', methods=['GET'])
    def api_supervisor_notifications():
        """Get pending supervision requests for the logged-in supervisor"""
        if 'logged' not in session or session.get('role') not in ('Doctor', 'Assistant'):
            return api_unauthorized()
        notifs = Supervisor_notification.query.filter_by(supervisor_id=session['sid']).all()
        return jsonify([{
            "nid": n.nid,
            "from_id": n._from_id,
            "from_name": n._from_name,
            "action": n.action,
            "project_id": n.project_id
        } for n in notifs])

    @app.route('/api/v2/supervisor/respond/<int:nid>/<string:action>', methods=['POST'])
    def api_supervisor_respond(nid, action):
        """Supervisor accepts/rejects supervision request"""
        if 'logged' not in session or session.get('role') not in ('Doctor', 'Assistant'):
            return api_unauthorized()
        notif = Supervisor_notification.query.get(nid)
        if not notif or notif.supervisor_id != session['sid']:
            return api_not_found("Notification")
        project = Project.query.get(notif.project_id)
        if not project:
            return api_not_found("Project")
        if action == 'accept':
            # Check if already has same role
            if session['role'] == 'Doctor' and project.doctor:
                return jsonify({"error": "Project already has a Doctor"}), 400
            if session['role'] == 'Assistant' and project.assistent:
                return jsonify({"error": "Project already has an Assistant"}), 400
            if session['role'] == 'Doctor':
                project.doctor = session['sid']
            else:
                project.assistent = session['sid']
            project.status = "Approved"
            sup = Supervisor.query.get(session['sid'])
            sup.projects.append(project)
        else :
            project.status = "Rejected"
        db.session.delete(notif)
        data = request.get_json()
        if 'optional_comment' in data and data.get('optional_comment')!= "":
            message = Message(content=data.get('optional_comment'),direction=2,message_type='feedback',project_id=notif.project_id,supervisor_id=session['sid']) 
            db.session.add(message)
        db.session.commit()
        return jsonify({"message": f"Request {action}ed"})

    # ----------------------------------------------------------------------
    # Tasks (TODO)
    @app.route('/api/v2/tasks', methods=['GET'])
    def api_get_tasks():
        """Get tasks for the current student or for a specific project (if supervisor)"""
        if 'logged' not in session:
            return api_unauthorized()
        role = session.get('role')
        if role == 'Student':
            if not session.get('in_team'):
                return jsonify({"error": "Not in a team"}), 400
            tasks = Task.query.filter_by(student_id=session['pid']).all()
        else:  # supervisor
            project_id = request.args.get('project_id')
            if not project_id:
                return api_bad_request("Missing project_id for supervisor")
            # Verify supervisor is assigned to that project
            project = Project.query.get(project_id)
            if not project or (project.doctor != session['sid'] and project.assistent != session['sid']):
                return jsonify({"error": "Not authorized for this project"}), 403
            # Tasks of all members
            tasks = Task.query.filter(Task.project_id == project_id).all()
        return jsonify([{
            "tid": t.tid,
            "description": t.description,
            "status": t.status,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "student_id": t.student_id
        } for t in tasks])

    @app.route('/api/v2/tasks', methods=['POST'])
    def api_create_task():
        """Create a new task (student for self, or supervisor for team member)"""
        if 'logged' not in session:
            return api_unauthorized()
        data = request.get_json()
        if not data:
            return api_bad_request("Missing JSON")
        title = data.get('description')    
        description = data.get('title')
        deadline_str = data.get('deadline')
        assigned_to = data.get('assigned_to')
        project_id = data.get('project_id')
        if not description or not deadline_str:
            return api_bad_request("Description and deadline required")
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        role = session.get('role')
        if role == 'Student':
            if not session.get('in_team'):
                return jsonify({"error": "Not in a team"}), 400
            student_id = session['pid']
            project_id = session['project_id']
        else:
            # Supervisor must provide assigned_to and project_id
            if not assigned_to or not project_id:
                return api_bad_request("assigned_to and project_id required for supervisor")
            # Verify authorization
            project = Project.query.get(project_id)
            if not project or (project.doctor != session['sid'] and project.assistent != session['sid']):
                return jsonify({"error": "Not authorized"}), 403
            student_id = assigned_to
        task = Task(title=title,description=description, deadline=deadline, student_id=student_id, project_id=project_id)
        db.session.add(task)
        db.session.commit()
        return jsonify({"message": "Task created", "tid": task.tid}), 201

    @app.route('/api/v2/tasks/<int:tid>', methods=['PUT'])
    def api_change_task_status(tid):
        """Mark task as done"""
        if 'logged' not in session:
            return api_unauthorized()
        task = Task.query.get(tid)
        if not task:
            return api_not_found("Task")
        # Authorization: student can change own tasks, supervisor can change any in their project
        if session.get('role') == 'Student':
            if task.student_id != session['pid']:
                return jsonify({"error": "Not authorized"}), 403
        else:
            project = Project.query.get(task.project_id)
            if not project or (project.doctor != session['sid'] and project.assistent != session['sid']):
                return jsonify({"error": "Not authorized"}), 403
        data = request.get_json()
        if proof_note == data['proof_note']:
            task.proof_note = proof_note
        if proof_link == data['proof_link']:
            task.proof_link = proof_link
        if data['status'] == "Done":
            task.status = "Done"
        db.session.commit()
        return jsonify({"message": "Task info successfully!"})

    @app.route('/api/v2/tasks/<int:tid>', methods=['DELETE'])
    def api_delete_task(tid):
        """Delete a task (same auth as change status)"""
        if 'logged' not in session:
            return api_unauthorized()
        task = Task.query.get(tid)
        if not task:
            return api_not_found("Task")
        if session.get('role') == 'Student':
            if task.student_id != session['pid']:
                return jsonify({"error": "Not authorized"}), 403
        else:
            project = Project.query.get(task.project_id)
            if not project or (project.doctor != session['sid'] and project.assistent != session['sid']):
                return jsonify({"error": "Not authorized"}), 403
        db.session.delete(task)
        db.session.commit()
        return jsonify({"message": "Task deleted"})

    # ----------------------------------------------------------------------
    # Meetings (schedule, list)
    @app.route('/api/v2/meetings', methods=['GET'])
    def api_get_meetings():
        """List meetings (supervisor sees all, student sees own project meetings)"""
        if 'logged' not in session:
            return api_unauthorized()
        role = session.get('role')
        if role in ('Doctor', 'Assistant'):
            meetings = Meeting.query.all()
        else:
            if not session.get('project_id'):
                return jsonify({"meetings": []})
            meetings = Meeting.query.filter_by(project_id=session['project_id']).all()
        return jsonify([{
            "mid": m.mid,
            "title": m.title,
            "notes": m.notes,
            "date": m.date.isoformat(),
            "time": m.time.isoformat(),
            "place": m.place,
            "location": m.location,
            "link": m.link,
            "project_id": m.project_id
        } for m in meetings])

    @app.route('/api/v2/meetings', methods=['POST'])
    def api_schedule_meeting():
        """Schedule a meeting (supervisor only, for their project)"""
        if 'logged' not in session or session.get('role') not in ('Doctor', 'Assistant'):
            return api_unauthorized()
        data = request.get_json()
        required = ['title', 'date', 'time', 'place', 'project_id']
        if not data or not all(k in data for k in required):
            return api_bad_request(f"Missing required fields: {required}")
        project = Project.query.get(data['project_id'])
        if not project or (project.doctor != session['sid'] and project.assistent != session['sid']):
            return jsonify({"error": "Not authorized for this project"}), 403
        meeting = Meeting(
            title=data['title'],
            notes=data.get('notes'),
            date=datetime.strptime(data['date'], "%Y-%m-%d").date(),
            time=datetime.strptime(data['time'], "%H:%M").time(),
            place=data['place'],
            location=data.get('location'),
            link=data.get('link'),
            project_id=data['project_id'],
            supervisor=session['sid']
        )
        db.session.add(meeting)
        db.session.commit()
        return jsonify({"message": "Meeting scheduled", "mid": meeting.mid}), 201

    # ----------------------------------------------------------------------
    # Notifications (student and supervisor)
    @app.route('/api/v2/notifications', methods=['GET'])
    def api_get_notifications():
        """Get all notifications for current user (student or supervisor)"""
        if 'logged' not in session:
            return api_unauthorized()
        role = session.get('role')
        if role == 'Student':
            notifs = Notification.query.filter_by(student_id=session['pid']).all()
            return jsonify([{
                "nid": n.nid,
                "action": n.action,
                "from_id": n._from_id,
                "from_name": n._from_name,
                "project_id": n.project_id,
                "max team size" : n.project.intended_team_size if n.project and n.project.intended_team_size else 6,
                "number of members" : n.project.members.count(),
                "project name": n.project.name,
                "project leader": n.project.leader,
                "read": n.read
            } for n in notifs])
        else:
            notifs = Supervisor_notification.query.filter_by(supervisor_id=session['sid']).all()
            return jsonify([{
                "nid": n.nid,
                "action": n.action,
                "from_id": n._from_id,
                "from_name": n._from_name,
                "read": n.read
            } for n in notifs])

    @app.route('/api/v2/edit_projects_limit', methods=['POST'])
    def edit_projects_limit():
        data = request.get_json()
        supervisor_id = data.get('supervisor_id')
        new_limit = data.get('new_limit')

        Supervisor.query.get_or_404(supervisor_id).projects_limit = new_limit
        db.session.commit()    
        return jsonify('Edited Successfully!')
    # ----------------------------------------------------------------------
    # Messages
    @app.route('/api/v2/messages', methods=['POST'])
    def api_send_message():
        """Send a message between student and supervisor"""
        if 'logged' not in session:
            return api_unauthorized()
        data = request.get_json()
        content = data.get('content')
        project_id = data.get('project_id')
        if not content or not project_id:
            return api_bad_request("content and project_id required")
        role = session.get('role')
        if role == 'Student':
            supervisor_id = data.get('supervisor_id')
            if not supervisor_id:
                return api_bad_request("supervisor_id required")
            # Verify student belongs to project
            if session.get('project_id') != project_id:
                return jsonify({"error": "You are not a member of this project"}), 403
            direction = 1
            sup = Supervisor.query.get(supervisor_id)
            if not sup:
                return api_not_found("Supervisor")
            msg = Message(direction=direction, project_id=project_id, content=content,
                        supervisor_id=supervisor_id)
        else:
            # Supervisor
            direction = 2
            # Verify supervisor is assigned to project
            project = Project.query.get(project_id)
            if not project or (project.doctor != session['sid'] and project.assistent != session['sid']):
                return jsonify({"error": "Not authorized for this project"}), 403
            msg = Message(direction=direction, project_id=project_id, content=content,
                        supervisor_id=session['sid'])
        db.session.add(msg)
        db.session.commit()
        return jsonify({"message": "Message sent", "mid": msg.mid}), 201

    @app.route('/api/v2/messages/<int:project_id>', methods=['GET'])
    def api_get_messages(project_id):
        """Get all messages for a project (members and supervisors)"""
        if 'logged' not in session:
            return api_unauthorized()
        role = session.get('role')
        if role == 'Student':
            if session.get('project_id') != project_id:
                return jsonify({"error": "Not a member of this project"}), 403
        else:
            project = Project.query.get(project_id)
            if not project or (project.doctor != session['sid'] and project.assistent != session['sid']):
                return jsonify({"error": "Not authorized"}), 403
        messages = Message.query.filter_by(project_id=project_id).order_by(Message.mid).all()
        return jsonify([{
            "mid": m.mid,
            "direction": m.direction,
            "content": m.content,
            "supervisor_id": m.supervisor_id,
            "message_type": m.message_type
        } for m in messages])
    @app.route('/api/v2/console', methods=['GET'])
    def api_console():
        return render_template('console.html')
    
    @app.route('/api/v2/student_status', methods=['PUT'])
    def student_status():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        student_id = data.get("student_id", "")
        student_status  = data.get("status", "")

        Student.query.get_or_404(student_id).status = student_status

        db.session.commit()
        return jsonify({"message": "Status updated"})

    @app.route('/api/v2/project_status', methods=['PUT'])
    def project_status():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        project_id = data.get("project_id", "").strip()
        project_status  = data.get("project_status", "").strip()

        Project.query.get_or_404(project_id).status = project_status

        db.session.commit()
        return jsonify({"message": "Status updated"})

    @app.route('/api/v2/create-discussion', methods=['POST'])
    def api_create_discussion():
        """Create a new discussion from JSON payload."""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400

        # Required fields
        required = ['date', 'time', 'location', 'project_id', 'discussion_number', 'supervisors']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Parse date and time
        try:
            discussion_date = date.fromisoformat(data['date'])
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        discussion_time = time.fromisoformat(data['time'])
        location = data['location'].strip()
        project_id = int(data['project_id'])
        number = int(data['discussion_number'])
        supervisors = data['supervisors']  # expected list of ints, e.g. [1,2,3]
        if not isinstance(supervisors, list):
            return jsonify({'error': 'supervisors must be a list of IDs'}), 400

        # Create the discussion
        discussion = Discussion(
            number=number,
            project_id=project_id,
            time=discussion_time,
            date=discussion_date,
            location=location
        )
        db.session.add(discussion)
        db.session.flush()  # to get the ID without committing

        # Set supervisors (store as JSON)
        discussion.set_supervisors(supervisors)

        # Create notification message
        content = f"The next discussion for this project will be on {data['date']} at {data['time']} in {location}"
        message = Message(
            direction=2,
            project_id=project_id,
            content=content,
            supervisor_id=session.get('sid'),
            message_type='feedback'
        )
        db.session.add(message)
        db.session.commit()

        # Return the created discussion data
        return jsonify({
            'message': 'Discussion created successfully',
            'discussion': {
                'id': discussion.did,
                'number': discussion.number,
                'date': discussion.date.isoformat(),
                'time': discussion.time.isoformat(),
                'location': discussion.location,
                'project_id': discussion.project_id,
                'supervisors': supervisors
            }
        }), 201
        
    @app.route('/api/v2/discussions', methods=['GET'])
    def api_list_discussions():
        """Return all discussions with project and supervisor info."""
        discussions = Discussion.query.order_by(Discussion.date.asc(), Discussion.time.asc()).all()
        result = []
        for d in discussions:
            supervisor_ids = d.get_supervisors()  # returns list of ints
            supervisor_names = []
            for sid in supervisor_ids:
                sup = Supervisor.query.get(sid)
                if sup:
                    supervisor_names.append(sup.name)
            project = Project.query.get(d.project_id)
            result.append({
                'id': d.did,
                'number': d.number,
                'date': d.date.isoformat(),
                'time': d.time.isoformat(),
                'location': d.location,
                'project_id': d.project_id,
                'project_name': project.name if project else None,
                'supervisors': supervisor_names
            })
        return jsonify(result), 200
    @app.route('/api/v2/discussions/<int:project_id>', methods=['GET'])
    def api_project_discussions(project_id):
        discussions = Discussion.query.filter_by(project_id=project_id).order_by(Discussion.date.asc(), Discussion.time.asc()).all()
        result = []
        for d in discussions:
            supervisor_ids = d.get_supervisors()  # returns list of ints
            supervisor_names = []
            for sid in supervisor_ids:
                sup = Supervisor.query.get(sid)
                if sup:
                    supervisor_names.append(sup.name)
            project = Project.query.get(d.project_id)
            result.append({
                'id': d.did,
                'number': d.number,
                'date': d.date.isoformat(),
                'time': d.time.isoformat(),
                'location': d.location,
                'project_id': d.project_id,
                'project_name': project.name if project else None,
                'supervisors': supervisor_names
            })
        return jsonify(result), 200
    @app.route('/api/v2/admin-panel', methods=['POST'])
    def admin_panel_api():
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Request must be JSON'}), 400

        min_team_size = data.get('min_team_size')
        max_team_size = data.get('max_team_size')
        max_projects_per_supervisor = data.get('max_projects_per_supervisor')
        comparison_years = data.get('comparison_years')
        documentation_deadline = data.get('documentation_deadline')
        ideas_deadline = data.get('ideas_deadline')
        results_announcement_date = data.get('results_announcement_date')

        required_fields = [
            min_team_size, max_team_size, max_projects_per_supervisor,
            comparison_years, documentation_deadline, ideas_deadline,
            results_announcement_date
        ]
        if any(field is None for field in required_fields):
            return jsonify({'error': 'All fields are required'}), 400

        try:
            min_team_size = int(min_team_size)
            max_team_size = int(max_team_size)
            max_projects_per_supervisor = int(max_projects_per_supervisor)
            comparison_years = int(comparison_years)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid numeric values'}), 400

        if min_team_size < 1:
            return jsonify({'error': 'Minimum team size must be at least 1'}), 400
        if max_team_size < min_team_size:
            return jsonify({'error': 'Maximum team size cannot be less than minimum team size'}), 400
        if max_team_size > 10:
            return jsonify({'error': 'Maximum team size cannot exceed 10'}), 400

        if max_projects_per_supervisor < 1:
            return jsonify({'error': 'Maximum projects per supervisor must be at least 1'}), 400
        if max_projects_per_supervisor > 20:
            return jsonify({'error': 'Maximum projects per supervisor cannot exceed 20'}), 400


        if comparison_years < 0:
            return jsonify({'error': 'Comparison years cannot be negative'}), 400
        if comparison_years > 10:
            return jsonify({'error': 'Comparison years cannot exceed 10'}), 400

        today = datetime.now().date()
        try:
            doc_deadline = datetime.strptime(documentation_deadline, '%Y-%m-%d').date()
            ideas_deadline_date = datetime.strptime(ideas_deadline, '%Y-%m-%d').date()
            results_date = datetime.strptime(results_announcement_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        if doc_deadline < today:
            return jsonify({'error': 'Documentation deadline cannot be in the past'}), 400
        if ideas_deadline_date < today:
            return jsonify({'error': 'Ideas deadline cannot be in the past'}), 400
        if results_date < today:
            return jsonify({'error': 'Results announcement date cannot be in the past'}), 400

        global MINTEAMSIZE, MAXTEAMSIZE, MAXPROJECTSPERSUPERVISOR
        global COMPARISONYEARS, DOCUMENTATIONDEADLINE, IDEASDEADLINE, RESULTSANNOUNCEMENTDATE

        MINTEAMSIZE = min_team_size
        MAXTEAMSIZE = max_team_size
        MAXPROJECTSPERSUPERVISOR = max_projects_per_supervisor
        COMPARISONYEARS = comparison_years
        DOCUMENTATIONDEADLINE = documentation_deadline
        IDEASDEADLINE = ideas_deadline
        RESULTSANNOUNCEMENTDATE = results_announcement_date

        return jsonify({
            'message': 'Settings updated successfully!',
            'updated': {
                'min_team_size': MINTEAMSIZE,
                'max_team_size': MAXTEAMSIZE,
                'max_projects_per_supervisor': MAXPROJECTSPERSUPERVISOR,
                'comparison_years': COMPARISONYEARS,
                'documentation_deadline': DOCUMENTATIONDEADLINE,
                'ideas_deadline': IDEASDEADLINE,
                'results_announcement_date': RESULTSANNOUNCEMENTDATE
            }
        }), 200

    @app.route('/api/v2/show_grades/<int:project_id>', methods=['GET'])
    def show_grades(project_id):
        project = Project.query.get_or_404(project_id) 
        show = False
        results = []
        for member in project.members:
            degree = getattr(member, 'finel_project_degree', None)  # adjust attribute name if different
            
            if degree is not None:
                show = True
                percentage = (degree / 180) * 100
                
                # Letter grade logic (exactly as in template)
                if percentage >= 96:
                    letter = 'A+'
                elif percentage >= 92:
                    letter = 'A'
                elif percentage >= 88:
                    letter = 'A-'
                elif percentage >= 84:
                    letter = 'B+'
                elif percentage >= 80:
                    letter = 'B'
                elif percentage >= 76:
                    letter = 'B-'
                elif percentage >= 72:
                    letter = 'C+'
                elif percentage >= 68:
                    letter = 'C'
                elif percentage >= 64:
                    letter = 'C-'
                elif percentage >= 60:
                    letter = 'D+'
                elif percentage >= 55:
                    letter = 'D'
                elif percentage >= 50:
                    letter = 'D-'
                else:
                    letter = 'F'
                
                results.append({
                    'name': member.name,
                    'degree': degree,
                    'percentage': round(percentage, 1),
                    'letter': letter,
                    'total': 180
                })
            else:
                results.append({
                    'name': member.name,
                    'degree': None,
                    'percentage': None,
                    'letter': None,
                    'total': 180
                })
        if show :
            return jsonify(results),200
        else : 
            return jsonify({"error":"Not set yet!"}),400

    @app.route('/api/v2/first_discussion/<int:project_id>', methods=['POST'])
    def api_first_discussion(project_id):
        project = Project.query.get_or_404(project_id)
        if 'role' not in session:
            api_unauthorized()
        if session.get('role') not in ['Doctor','Assistant'] and project.doctor != session['sid']:
            return jsonify({"error":"Not a supervisor in this project!"})
        data = request.get_json()
        for member in project.members : 
            member.first_descussion_result = data[str(member.pid)] if data[str(member.pid)] else 1000
        if 'special' in data : 
            is_special = data.get('special') == 'True'
            project.special = is_special
        if data.get('feedback1') and data.get('feedback1') != '' :
                message1 = Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=data.get('feedback1'),message_type='feedback')
                db.session.add(message1)
        if data.get('feedback2') and data.get('feedback2') != '' :
                message2= Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=data.get('feedback2'),message_type='feedback')
                db.session.add(message2)

        discussions = Discussion.query.filter_by(project_id=project_id).all()
        for discussion in discussions :
            db.session.delete(discussion)  
        db.session.commit()
        return jsonify({"info":"Saved successfully!"})
    
    @app.route('/api/v2/second_discussion/<int:project_id>', methods=['POST'])
    def api_second_discussion(project_id):
        project = Project.query.get_or_404(project_id)
        if 'role' not in session:
            api_unauthorized()
        if session.get('role') not in ['Doctor','Assistant'] and project.doctor != session['sid']:
            return jsonify({"error":"Not a supervisor in this project!"})
        data = request.get_json()
        for member in project.members : 
            member.finel_project_degree = data[str(member.pid)] if data[str(member.pid)] else 1000
        if 'special' in data : 
            is_special = data.get('special') == 'True'
            project.special = is_special
        if data.get('feedback1') and data.get('feedback1') != '' :
                message1 = Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=data.get('feedback1'),message_type='feedback')
                db.session.add(message1)
        if data.get('feedback2') and data.get('feedback2') != '' :
                message2= Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=data.get('feedback2'),message_type='feedback')
                db.session.add(message2)

        discussions = Discussion.query.filter_by(project_id=project_id).all()
        for discussion in discussions :
            db.session.delete(discussion)  
        db.session.commit()
        return jsonify({"info":"Saved successfully!"})
#============== AI Model =================

    @app.route('/api/check-similarity', methods=['POST'])
    def check_similarity():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        project_name = data.get("project_name", "").strip()
        description  = data.get("description", "").strip()

        if not project_name and not description:
            return jsonify({"error": "Provide at least project_name or description"}), 400

        db_projects = Project.query.filter(Project.name!=project_name,Project.description!=description).all()

        if not db_projects:
            return jsonify({"is_similar": False, "similar_projects": []})

        rows = []
        for p in db_projects:
            rows.append({
                "project_name": p.name        or "",
                "description":  p.description or "",
            })

        projects_df = pd.DataFrame(rows)

        # Build the combined "project_name. description" text column
        projects_df["input_text"] = projects_df.apply(
            lambda row: build_project_text(row["project_name"], row["description"]),
            axis=1,
        )

        # Drop rows where both name and description were empty
        projects_df = projects_df[projects_df["input_text"].astype(bool)].reset_index(drop=True)

        if projects_df.empty:
            return jsonify({"is_similar": False, "similar_projects": []})

        # Build the text for the NEW project
        new_project_text = build_project_text(project_name, description)

        # Run the similarity check
        model = get_embedding_model()

        similarity_system = SimilaritySystem(
            projects=projects_df,
            model=model,
        )

        result = similarity_system.find_similar_projects(new_project_text)
        similar_projects = result["similar_projects"]

        # is_similar = True if ANY match is above the 0.7 threshold
        # (SimilaritySystem already filters by threshold internally;
        #  if nothing passes, it returns the single closest match with a low score)
        THRESHOLD = 0.7
        is_similar = any(m["score"] >= THRESHOLD for m in similar_projects)

        return jsonify({
            "is_similar": is_similar,
            "similar_projects": similar_projects,
        })