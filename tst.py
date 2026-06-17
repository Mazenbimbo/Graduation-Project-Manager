# student : first_descussion_result - second_descussion_result 
# project :
# message (feedback)

# project = Project.query.get_or_404(project_id)
# if session['sid'] != project.doctor :
#   flash("You are not a supervisor in this project","error")
#   return redirect('/project/project_id')
# for member in project.members : 
#    member.first_descussion_result = request.form.get(f'degree-for-{member.pid}')
# message1 = Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=request.form.get('feedback1'),message_type='feedback')
# message2 = Message(direction=2,supervisor_id=session['sid'],project_id=project_id,content=request.form.get('feedback1'),message_type='feedback')
# db.session.save(message1)
# db.session.save(message2)
# db.session.commit()