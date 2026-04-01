"""
新南方职业培训学院 自动登录 + 签到脚本（多账号版）
使用方法: python3 xnfedu_checkin.py
"""

import requests
import re
import sys
from datetime import datetime

# ==================== 配置区 ====================
# 多账号配置：添加更多账号只需在列表中增加 {"username": "xxx", "password": "xxx"}
ACCOUNTS = [
    {"username": "user1", "password": "password"},
    {"username": "user2", "password": "password"},
    #{"username": "user3", "password": "password"},
]
# ================================================

def extract_value(text, field_name):
    """从HTML中提取指定name属性的value值（用于获取ASP.NET的隐藏字段）"""
    pattern = rf'name="{field_name}"[^>]*value="([^"]*)"'
    match = re.search(pattern, text)
    return match.group(1) if match else ''

def login(session, username, password):
    """执行登录流程，成功则返回TOKEN"""
    login_url = 'https://jxedu.xnfedu.com/Student/Login.aspx'
    resp = session.get(login_url)
    if resp.status_code != 200:
        return None, f"无法访问登录页面 (状态码: {resp.status_code})"

    # 构建登录POST数据    
    data = {
        '__VIEWSTATE': extract_value(resp.text, '__VIEWSTATE'),
        '__VIEWSTATEGENERATOR': extract_value(resp.text, '__VIEWSTATEGENERATOR'),
        '__EVENTVALIDATION': extract_value(resp.text, '__EVENTVALIDATION'),
        'ctl00$WorkContent$txtLoginAccount': username,
        'ctl00$WorkContent$txtPassword': password,
        'ctl00$WorkContent$LoginButton': '马上登录'
    }
    
    resp = session.post(login_url, data=data, allow_redirects=True)

    # 判断登录是否成功：成功登录后会跳转到包含TOKEN的URL    
    if 'Login.aspx' in resp.url and 'TOKEN' not in resp.url:
        if '密码输入错误' in resp.text:
            return None, "登录失败: 密码错误"
        return None, "登录失败: 未知原因"

    # 从跳转后的URL中提取TOKEN   
    token_match = re.search(r'TOKEN=([^&]+)', resp.url)
    token = token_match.group(1) if token_match else None
    return token, "登录成功"

def get_red_beans(session, token):
    """访问个人中心页面，并解析出剩余红豆和累计红豆数量"""
    personal_url = f'https://jxedu.xnfedu.com/student/personal.aspx?TOKEN={token}'
    resp = session.get(personal_url)
    if resp.status_code != 200:
        return None, None
    
    # 剩余红豆
    remain_match = re.search(r'id="WorkContent_WorkContent_lab剩余红豆[^"]*"[^>]*>(\d+)', resp.text)
    # 累计红豆
    total_match = re.search(r'id="WorkContent_WorkContent_lab累计红豆[^"]*"[^>]*>(\d+)', resp.text)
    
    remain = remain_match.group(1) if remain_match else None
    total = total_match.group(1) if total_match else None
    return remain, total

def checkin(session, token):
    """执行签到操作，并返回结果和红豆信息"""
    index_url = f'https://jxedu.xnfedu.com/Portal/Index.aspx?TOKEN={token}'
    resp = session.get(index_url)
    if resp.status_code != 200:
        return False, f"无法访问首页 (状态码: {resp.status_code})", None, None
    
    if '今日已经签到' in resp.text:
        match = re.search(r'今日已经签到\+?(\d+)', resp.text)
        points = match.group(1) if match else '?'
        # 获取红豆数量
        remain, total = get_red_beans(session, token)
        return True, f"今日已签到过 (+{points}红豆)", remain, total
    
    if 'lbtnSign' not in resp.text and 'qd.png' not in resp.text:
        return False, "未找到签到按钮", None, None
    
    # 构建签到POST请求
    data = {
        '__VIEWSTATE': extract_value(resp.text, '__VIEWSTATE'),
        '__VIEWSTATEGENERATOR': extract_value(resp.text, '__VIEWSTATEGENERATOR'),
        '__EVENTVALIDATION': extract_value(resp.text, '__EVENTVALIDATION'),
        '__EVENTTARGET': 'ctl00$lbtnSign',
        '__EVENTARGUMENT': ''
    }
    
    resp = session.post(index_url, data=data, allow_redirects=True)
    
    # 判断签到结果
    if '签到成功' in resp.text or '今日已经签到' in resp.text:
        match = re.search(r'签到[^\+]*\+?(\d+)', resp.text)
        points = match.group(1) if match else '?'
        # 获取红豆数量
        remain, total = get_red_beans(session, token)
        return True, f"签到成功 (+{points}红豆)", remain, total
    elif 'MyAlert' in resp.text:
        alert = re.search(r"MyAlert\([^)]*?'([^']+)'", resp.text)
        if alert:
            return False, f"签到提示: {alert.group(1)}", None, None
    
    # 再次检查页面确认签到状态
    resp = session.get(index_url)
    if '今日已经签到' in resp.text:
        match = re.search(r'今日已经签到\+?(\d+)', resp.text)
        points = match.group(1) if match else '?'
        remain, total = get_red_beans(session, token)
        return True, f"签到成功 (+{points}红豆)", remain, total
    
    return False, "签到状态未知", None, None

def main():
    print("=" * 50)
    print("  新南方职业培训学院 - 自动签到（多账号版）")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  账号数量: {len(ACCOUNTS)}")
    print("=" * 50)
    
    results = []  # 记录结果
    
    for i, account in enumerate(ACCOUNTS, 1):
        username = account["username"]
        password = account["password"]
        
        print(f"\n[账号 {i}/{len(ACCOUNTS)}] {username}")
        print("-" * 40)
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        result = {"username": username, "status": "未知", "message": ""}
        
        try:
            print("  [1/2] 正在登录...")
            token, msg = login(session, username, password)
            print(f"        {msg}")
            
            if not token:
                result["status"] = "失败"
                result["message"] = "登录失败"
                print("  登录失败，跳过签到")
            else:
                print("  [2/2] 正在签到...")
                success, msg, remain, total = checkin(session, token)
                print(f"        {msg}")
                result["status"] = "成功" if success else "失败"
                result["message"] = msg
                if remain:
                    result["remain_beans"] = remain
                if total:
                    result["total_beans"] = total
        
        except Exception as e:
            result["status"] = "错误"
            result["message"] = str(e)
            print(f"  发生错误: {e}")
        
        results.append(result)
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("  签到汇总")
    print("=" * 50)
    success_count = sum(1 for r in results if r["status"] == "成功")
    for r in results:
        status_icon = "✓" if r["status"] == "成功" else "X"
        msg = r['message']
        if r.get('remain_beans') or r.get('total_beans'):
            beans_info = []
            if r.get('remain_beans'):
                beans_info.append(f"剩余{r['remain_beans']}")
            if r.get('total_beans'):
                beans_info.append(f"累计{r['total_beans']}")
            msg += f" | 红豆: {', '.join(beans_info)}"
        print(f"  {status_icon} {r['username']}: {msg}")
    print(f"\n  成功: {success_count}/{len(results)}")
    print("=" * 50)
    input("\n按回车键退出...")

if __name__ == '__main__':
    main()
