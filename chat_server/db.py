import pymongo
import settings

mongo = pymongo.MongoClient(settings.MONGO_URI)

# legals_cursor = mongo.Users.Legal_team.find()
# for legal in legals_cursor:
#     r = legal['reporting_users']
#     r.append('12345')
#     print(r.append('12'))
#     break