from django.db import migrations

def fwd(apps, s): apps.get_model("tickets","Ticket").objects.filter(status="CLOSED").update(status="COMPLETED")
def rev(apps, s): apps.get_model("tickets","Ticket").objects.filter(status="COMPLETED").update(status="CLOSED")

class Migration(migrations.Migration):
    dependencies = [("tickets","0003_alter_ticket_status")]
    operations = [migrations.RunPython(fwd, rev)]
