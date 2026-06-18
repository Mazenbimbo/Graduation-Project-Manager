# student : first_descussion_result - second_descussion_result 
# project :
# message (feedback)

# if request.method == 'GET':
#   projects = Project.query.all()
#   supervisors = Supervisor.query.all()
#   return render_template('new_discussion.html',projects=projects=supervisors=supervisors)
# discussion_date = request.form.get('date')
# discussion_time = request.form.get('time')
# location = request.form.get('location').strip() or None

# discussion_date = date.fromisoformat(discussion_date)
# discussion_time = time.fromisoformat(discussion_time)
# supervisors = request.form.get('supervisors')
# project_id = request.form.get('project')
# number = request.form.get('number')
# discussion = Discussion(number=number,project_id=project_id,time=discussion_time,date=discussion_date,location=location)
# db.session.add(discussion)
# db.session.commit()
# discussion = Discussion.query.filter_by(number=number,project_id=project_id,time=discussion_time,date=discussion_date,location=location)
# discussion.set_supervisors(supervisors)
# content = f"The next discussion for this project will be in {discussion_date} {discussion_time} in {location}"
# message =  Message(direction=2,project_id=project_id,content=content,supervisor_id=session['sid'],message_type='feedback')
# db.session.commit()
# flash("Created successfully!","info")
# return "created"