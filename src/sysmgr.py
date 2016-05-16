import re, string, os

configPath = {"docklet": os.environ.get("DOCKLET_CONF")+"/docklet.conf",
    "container": os.environ.get("DOCKLET_CONF")+"/container.conf"}
#configPath = "../conf/docklet.conf"
#lxcconfigPath = "../conf/container.conf"
defaultPattern = re.compile(u'# *\S+ *= *\S+')
activePattern = re.compile(u'\S+ *= *\S+')
historyPattern = re.compile(u'## *\S+ *= *\S+')

def parse_line(line):
    kind = ""
    parm = ""
    val = ""
    if defaultPattern.match(line) != None and not "==" in line:
        kind = "default"
    elif activePattern.match(line) != None and not "#" in line:
        kind = "active"
    elif historyPattern.match(line) != None and not "==" in line:
        kind = "history"
    if kind != "":
        line = line.replace("#", "").replace("\n", "")
        parm = line[:line.find("=")].strip()
        val = line[line.find("=")+1:].strip()
    return [kind, parm, val]

class SystemManager():

    def getParmList(*args, **kwargs):
        result = {"docklet": "", "container": ""}
        for field in ["docklet", "container"]:
            configFile = open(configPath[field])
            lines = configFile.readlines()
            configFile.close()
            conf = {}
            for line in lines:
                [linekind, lineparm, lineval] = parse_line(line)
                if linekind == "default":
                    conf[lineparm] = {"val": "novalidvaluea", "default": lineval, "history": []}
            for line in lines:
                [linekind, lineparm, lineval] = parse_line(line)
                if linekind == "active":
                    try:
                        conf[lineparm]["val"] = lineval
                    except:
                        conf[lineparm] = {"val": lineval, "default": lineval, "history": []}
            for line in lines:
                [linekind, lineparm, lineval] = parse_line(line)
                if linekind == "history":
                    conf[lineparm]["history"].append(lineval)
            result[field] = [({'parm': parm, 'val': conf[parm]['val'], 
                'default': conf[parm]['default'], "history": conf[parm]['history']}) for parm in sorted(conf.keys())]
        return result

    # 1. def and not act 2. act and not def 3. def and act
    # have def and act and hist
    def modify(self, field, parm, val):
        configFile = open(configPath[field])
        lines = configFile.readlines()
        configFile.close()
        finish = False
        for i in range(0, len(lines)):
            line = lines[i]
            [linekind, lineparm, lineval] = parse_line(line)
            if linekind == "active" and lineparm == parm:
                lines[i] = "## " + parm + "=" + lineval + "\n" 
                lines.insert(i, parm + "=" + val + "\n")
                if i == 0 or not parm in lines[i-1] or not "=" in lines[i-1]:
                    lines.insert(i, "# " + parm + "=" + lineval + "\n")
                finish = True
                break
        if finish == False:
            for i in range(0, len(lines)):
                line = lines[i]
                [linekind, lineparm, lineval] = parse_line(line)
                if linekind == "default" and parm == lineparm:
                    lines.insert(i+1, parm + "="  + val + "\n")
                    break
        for i in range(0, len(lines)):
            line = lines[i]
            [linekind, lineparm, lineval] = parse_line(line)
            if linekind == "history" and parm == lineparm and val == lineval:
                lines.pop(i)
                break
        configFile = open(configPath[field], "w")
        for line in lines:
            configFile.write(line)
        configFile.close()
        return [True, ""]

    def clear(self, field, parm):
        configFile = open(configPath[field])
        lines = configFile.readlines()
        configFile.close()
        finish = False
        for i in range(0, len(lines)):
            line = lines[i]
            [linekind, lineparm, lineval] = parse_line(line)
            if linekind == "history" and parm == lineparm:
                lines[i] = ""
        configFile = open(configPath[field], "w")
        for line in lines:
            configFile.write(line)
        configFile.close()
        return [True, ""]

    def add(self, field, parm, val):
        configFile = open(configPath[field], "a")
        configFile.write("\n" + "# " + parm + "=" + val + "\n" + parm + "=" + val + "\n")
        configFile.close()
        return [True, ""]

    def delete(self, field, parm):
        configFile = open(configPath[field])
        lines = configFile.readlines()
        configFile.close()
        for i in range(0, len(lines)):
            line = lines[i]
            if parm in line:
                lines[i] = ""
        configFile = open(configPath[field], "w")
        for line in lines:
            configFile.write(line)
        configFile.close()
        return [True, ""]

    def reset_all(self, field):
        configFile = open(configPath[field])
        lines = configFile.readlines()
        configFile.close()
        conf = {}
        for line in lines:
            [linekind, lineparm, lineval] = parse_line(line)
            if linekind == "default":
                conf[lineparm] = {"val": lineval, "default": lineval, "history": []}
        for line in lines:
            [linekind, lineparm, lineval] = parse_line(line)
            if linekind == "active":
                try:
                    conf[lineparm]["val"] = lineval
                except:
                    conf[lineparm] = {"val": lineval, "default": lineval, "history": []}
        for line in lines:
            [linekind, lineparm, lineval] = parse_line(line)
            if linekind == "history":
                conf[lineparm]["history"].append(lineval)

        for i in range(0, len(lines)):
            line = lines[i]
            if activePattern.match(line) != None and not "#" in line:
                segs = line.replace("\n", "").split("=")
                lines[i] = segs[0].strip() + "=" + conf[segs[0].strip()]["default"] + "\n" 
            elif historyPattern.match(line) != None and not "==" in line:
                lines[i] = ""
        configFile = open(configPath[field], "w")
        for line in lines:
            configFile.write(line)
        configFile.close()
        return [True, ""]

#sysmgr = SystemManager()
#print(sysmgr.getParmList())

