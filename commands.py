import datetime
import random
import re
import threading
import time

import emoji

import utility as util
import database as opt
import schemes
import messages

db = opt.MongoDatabase
bot_start = time.time()

### User Commands ###

def ping(channel):
    util.send_message(messages.pong, channel)

def commands(channel):
    util.send_message(messages.commands, channel)

def enter_dungeon(user, channel):
    user = db(opt.USERS).find_one_by_id(user)
    display_name = util.get_display_name(user['_id'])
    if user and user.get('user_level'):
        enter_time = time.time()
        if int(user['next_entry'] - enter_time) <= 0:
            dungeon = db(opt.GENERAL).find_one_by_id(0)
            dungeon_level = dungeon['dungeon_level']
            user_level = user['user_level']

            if user_level > dungeon_level:
                level_run = dungeon_level
                success_rate = 65+((user_level-dungeon_level)*7)
                success_rate = success_rate if success_rate <= 100 else 100
                experience_gain = int(100*dungeon_level)*(1-((user_level-dungeon_level))*0.2)
                experience_gain = experience_gain if experience_gain >= 0 else 0
                dungeon_timeout = 600
            else:
                level_run = user_level
                success_rate = 65
                experience_gain = int(100*user_level)
                dungeon_timeout = 600

            if experience_gain == 0:
                util.send_message(messages.dungeon_too_low_level(display_name, str(dungeon_level)), channel)
                return

            dungeon_success = random.randint(1, 101)
            db(opt.USERS).update_one(user['_id'], {'$set': {
                'entered': 1,
                'last_entry': enter_time,
                'next_entry': enter_time + dungeon_timeout
            }})

            if dungeon_success <= success_rate:
                run_quality = random.randint(1, 101)
                if run_quality <= 10:
                    experience_gain = int(experience_gain*0.5)
                    try:
                        message = emoji.emojize(list(db(opt.TEXT).get_random_documents_by_match({'mode': 'vbr'}, 1))[0]['text'])
                    except:
                        message = 'Very Bad Run'
                    util.send_message(messages.dungeon_very_bad_run(display_name, message, str(experience_gain)), channel)
                elif run_quality >= 90:
                    experience_gain = int(experience_gain*1.5)
                    try:
                        message = emoji.emojize(list(db(opt.TEXT).get_random_documents_by_match({'mode': 'vgr'}, 1))[0]['text'])
                    except:
                        message = 'Very Good Run'
                    util.send_message(messages.dungeon_very_good_run(display_name, message, str(experience_gain)), channel)
                else:
                    run_quality = random.randint(75,126)
                    experience_gain = int(experience_gain*run_quality*0.01)
                    if run_quality < 100:
                        try:
                            message = emoji.emojize(list(db(opt.TEXT).get_random_documents_by_match({'mode': 'br'}, 1))[0]['text'])
                        except:
                            message = 'Bad Run'
                        util.send_message(messages.dungeon_bad_run(display_name, message, str(experience_gain)), channel)
                    else:
                        try:
                            message = emoji.emojize(list(db(opt.TEXT).get_random_documents_by_match({'mode': 'gr'}, 1))[0]['text'])
                        except:
                            message = 'Good Run'
                        util.send_message(messages.dungeon_good_run(display_name, message, str(experience_gain)), channel)
                db(opt.USERS).update_one(user['_id'], {'$inc': {
                    'total_experience': experience_gain,
                    'current_experience': experience_gain,
                    'dungeon_wins': 1
                }})
                db(opt.GENERAL).update_one(0, {'$inc': {
                    'total_experience': experience_gain,
                    'total_wins': 1
                }})
                user_experience = user['current_experience'] + experience_gain
                if (((user_level+1)**2)*100) - user_experience <= 0:
                    db(opt.USERS).update_one(user['_id'], {'$inc': {
                        'user_level': 1,
                        'current_experience': -(((user['user_level']+1)**2)*100)
                    }})
                    level_up_thread = threading.Thread(target = level_up, args=(display_name, str(user['user_level'] + 1), channel))
                    level_up_thread.start()
            else:
                db(opt.USERS).update_one(user['_id'], { '$inc': { 'dungeon_losses': 1 } })
                db(opt.GENERAL).update_one(0, { '$inc': { 'total_losses': 1 } })
                try:
                    message = emoji.emojize(list(db(opt.TEXT).get_random_documents_by_match({'mode': 'fail'}, 1))[0]['text'])
                except:
                    message = 'Failed Run'
                util.send_message(messages.dungeon_failed(display_name, message), channel)
            db(opt.USERS).update_one(user['_id'], { '$inc': { 'dungeons': 1 } })
            db(opt.GENERAL).update_one(0, { '$inc': { 'total_dungeons': 1 } })
        else:
            util.send_message(messages.dungeon_already_entered(display_name, str(datetime.timedelta(seconds=(int(user['next_entry']) - enter_time))).split('.')[0]), channel)
    else:
        util.send_message(messages.not_registered(display_name), channel)

def level_up(user, message, channel):
    util.queue_message(messages.user_level_up(user, message), 0, channel)

def dungeon_level(channel):
    dungeon = db(opt.GENERAL).find_one_by_id(0)
    util.send_message(messages.dungeon_level(str(dungeon['dungeon_level'])), channel)

def dungeon_master(channel):
    top_user = db(opt.USERS).find_one(sort=[('total_experience', -1)])
    if top_user and top_user.get('user_level'):
        highest_experience = top_user['total_experience']
        user_level = top_user['user_level']
        number_of_top_users = db(opt.USERS).count_documents( {'total_experience': highest_experience} )
        if number_of_top_users == 1:
            top_user = db(opt.USERS).find_one( {'total_experience': highest_experience} )
            util.send_message(messages.dungeon_master(util.get_display_name(top_user['_id']), str(user_level), str(highest_experience)), channel)
        else:
            util.send_message(messages.dungeon_masters(str(number_of_top_users), str(user_level), str(highest_experience)), channel)
    else:
        util.send_message(messages.dungeon_no_master, channel)

def dungeon_stats(channel):
    general = db(opt.GENERAL).find_one_by_id(0)
    try:
        dungeons = general['total_dungeons']
    except:
        dungeons = 0
    try:
        wins = general['total_wins']
    except:
        wins = 0
    try:
        losses = general['total_losses']
    except:
        losses = 0
    if dungeons == 1:
        dungeonword = ' Dungeon'
    else:
        dungeonword = ' Dungeons'
    if wins == 1:
        winword = ' Win'
    else:
        winword = ' Wins'
    if losses == 1:
        loseword = ' Loss'
    else:
        loseword = ' Losses'
    if dungeons is not 0:
        util.send_message(messages.dungeon_general_stats(str(dungeons), dungeonword, str(wins), winword, str(losses), loseword, str(round((((wins)/(dungeons))*100), 3))), channel)
    else:
        util.send_message(messages.dungeon_general_stats(str(dungeons), dungeonword, str(wins), winword, str(losses), loseword, '0'), channel)

def raid_stats(channel):
    general = db(opt.GENERAL).find_one_by_id(0)
    try:
        raids = general['total_raids']
    except:
        raids = 0
    try:
        wins = general['total_raid_wins']
    except:
        wins = 0
    try:
        losses = general['total_raid_losses']
    except:
        losses = 0
    if raids == 1:
        raidword = ' Raid'
    else:
        raidword = ' Raids'
    if wins == 1:
        winword = ' Win'
    else:
        winword = ' Wins'
    if losses == 1:
        loseword = ' Loss'
    else:
        loseword = ' Losses'
    if raids is not 0:
        util.send_message(messages.raid_general_stats(str(raids), raidword, str(wins), winword, str(losses), loseword, str(round((((wins)/(raids))*100), 3))), channel)
    else:
        util.send_message(messages.raid_general_stats(str(raids), raidword, str(wins), winword, str(losses), loseword, '0'), channel)

def bot_uptime(channel):
    uptime = time.time()
    util.send_message(messages.dungeon_uptime(str(datetime.timedelta(seconds=(int(uptime - bot_start))))), channel)

def register(user, channel, channel_id):
    registered = db(opt.USERS).find_one_by_id(user)
    if not registered or not registered.get('user_level'):
        db(opt.GENERAL).update_one(0, { '$inc': { 'dungeon_level': 1 } })
        db(opt.USERS).update_one(user, { '$set': schemes.USER }, upsert=True)
        dungeon = db(opt.GENERAL).find_one_by_id(0)
        util.queue_message(messages.user_register(util.get_display_name(user), str(dungeon['dungeon_level'])), 0, channel)
    else:
        try:
            user_cmdusetime = db(opt.USERS).find_one_by_id(user)['cmdusetime']
        except:
            user_cmdusetime = 0
        user_cooldown = db(opt.CHANNELS).find_one_by_id(channel_id)['user_cooldown']
        global_cmdusetime = db(opt.CHANNELS).find_one_by_id(channel_id)['cmdusetime']
        global_cooldown = db(opt.CHANNELS).find_one_by_id(channel_id)['global_cooldown']
        message_queued = db(opt.CHANNELS).find_one_by_id(channel_id)['message_queued']
        if time.time() > global_cmdusetime + global_cooldown and time.time() > user_cmdusetime + user_cooldown and message_queued == 0:
            db(opt.CHANNELS).update_one(channel_id, { '$set': { 'cmdusetime': time.time() } }, upsert=True)
            db(opt.USERS).update_one(user, { '$set': { 'cmdusetime': time.time() } }, upsert=True)
            util.send_message(messages.user_already_registered(util.get_display_name(user)), channel)

def user_experience(user, channel, message=None):
    if not message:
        registered = util.check_if_registered(user, channel)
        if registered:
            user = db(opt.USERS).find_one_by_id(user)
            util.send_message(messages.user_experience(util.get_display_name(user['_id']), str(user['total_experience'])), channel)
    else:
        target = util.get_user_id(message)
        if target:
            registered = util.check_if_registered(user, channel, target)
            if registered:
                target = db(opt.USERS).find_one_by_id(target)
                util.send_message(messages.user_experience(util.get_display_name(target['_id']), str(target['total_experience'])), channel)
        else:
            registered = util.check_if_registered(user, channel)
            if registered:
                user = db(opt.USERS).find_one_by_id(user)
                util.send_message(messages.user_experience(util.get_display_name(user['_id']), str(user['total_experience'])), channel)

def user_level(user, channel, message=None):
    if not message:
        registered = util.check_if_registered(user, channel)
        if registered:
            user = db(opt.USERS).find_one_by_id(user)
            util.send_message(messages.user_level(util.get_display_name(user['_id']), str(user['user_level']), str(user['current_experience']), str((((user['user_level']) + 1)**2)*100)), channel)
    else:
        target = util.get_user_id(message)
        if target:
            registered = util.check_if_registered(user, channel, target)
            if registered:
                target = db(opt.USERS).find_one_by_id(target)
                util.send_message(messages.user_level(util.get_display_name(target['_id']), str(target['user_level']), str(target['current_experience']), str((((target['user_level']) + 1)**2)*100)), channel)
        else:
            registered = util.check_if_registered(user, channel)
            if registered:
                user = db(opt.USERS).find_one_by_id(user)
                util.send_message(messages.user_level(util.get_display_name(user['_id']), str(user['user_level']), str(user['current_experience']), str((((user['user_level']) + 1)**2)*100)), channel)

def winrate(user, channel, message=None):
    if not message:
        registered = util.check_if_registered(user, channel)
        if registered:
            user = db(opt.USERS).find_one_by_id(user)
            if user['dungeons'] == 0:
                util.send_message(messages.no_entered_dungeons(util.get_display_name(user['_id'])), channel)
            else:
                dungeons = user['dungeons']
                wins = user['dungeon_wins']
                losses = user['dungeon_losses']

                if wins == 1:
                    win_word = ' Win'
                else:
                    win_word = ' Wins'
                if losses == 1:
                    lose_word = ' Loss'
                else:
                    lose_word = ' Losses'
                util.send_message(messages.user_stats(util.get_display_name(user['_id']), str(wins), win_word, str(losses), lose_word, str(round((((wins)/(dungeons))*100), 3))), channel)
    else:
        target = util.get_user_id(message)
        if user == target:
            same_user = True
        if target:
            registered = util.check_if_registered(user, channel, target)
            if registered:
                target = db(opt.USERS).find_one_by_id(target)
                if target['dungeons'] == 0:
                    if same_user:
                        util.send_message(messages.no_entered_dungeons(util.get_display_name(user)), channel)
                    else:
                        util.send_message(messages.user_no_entered_dungeons(util.get_display_name(user)), channel)
                else:
                    dungeons = target['dungeons']
                    wins = target['dungeon_wins']
                    losses = target['dungeon_losses']
                    if wins == 1:
                        win_word = ' Win'
                    else:
                        win_word = ' Wins'
                    if losses == 1:
                        lose_word = ' Loss'
                    else:
                        lose_word = ' Losses'
                    util.send_message(messages.user_stats(util.get_display_name(target['_id']), str(wins), win_word, str(losses), lose_word, str(round((((wins)/(dungeons))*100), 3))), channel)
        else:
            registered = util.check_if_registered(user, channel)
            if registered:
                user = db(opt.USERS).find_one_by_id(user)
                if user['dungeons'] == 0:
                    util.send_message(messages.no_entered_dungeons(util.get_display_name(user['_id'])), channel)
                else:
                    dungeons = user['dungeons']
                    wins = user['dungeon_wins']
                    losses = user['dungeon_losses']
                    if wins == 1:
                        win_word = ' Win'
                    else:
                        win_word = ' Wins'
                    if losses == 1:
                        lose_word = ' Loss'
                    else:
                        lose_word = ' Losses'
                    util.send_message(messages.user_stats(util.get_display_name(user['_id']), str(wins), win_word, str(losses), lose_word, str(round((((wins)/(dungeons))*100), 3))), channel)
