import copy
import ipaddress
import os
import subprocess
import sys
import time
from datetime import datetime
import json
from getpass import getpass
from json import JSONEncoder
from typing import Any

import icmplib


class Bucket:
    def __init__(self, id):
        self.id = id
        self.peers = []


class Query:
    def __init__(self, id, ts, uid):
        self.id = id
        self.answer = []
        self.create_time = ts
        self.child = []
        self.uid = uid
        self.parent = None


class Response:
    def __init__(self, id, ts, uid):
        self.id = id
        self.uid = uid
        self.create_time = ts
        self.parent = []


class Provider:
    def __init__(self, id, ts, uid):
        self.id = id
        self.uid = uid
        self.create_time = ts
        self.parent = None


class Address:
    def __init__(self, ip, ip_type, port, protocol):
        self.ip = ip
        self.ip_type = ip_type
        self.port = port
        self.protocol = protocol
        self.rtt = None
        self.ip_hop = None


class Stats:
    def __init__(self, cid, ipfs_hop, providers):
        self.cid = cid
        self.ipfs_hop = ipfs_hop
        self.providers = providers


class StatsEncoder(JSONEncoder):
    def default(self, o: Stats):
        json_string = o.__dict__
        providers = json_string['providers']
        providers_new = copy.deepcopy(providers)
        for key in providers.keys():
            providers_new[key] = [ob.__dict__ for ob in providers[key]]
        json_string['providers'] = providers_new
        return json_string


def add_parent(query_target: Query, q: Query):
    """
    add parents for q if exist
    :param query_target: query to check
    :param q: new query q
    :return: True if added to at least one node
    """
    for response in query_target.answer:
        if q.id == response.id:
            try:
                # case child exist
                index = query_target.child.index(q)
            except Exception:
                # case new child
                query_target.child.append(q)
            if q.parent is None:
                q.parent = [query_target]
            else:
                q.parent.append(query_target)
    if len(query_target.child) > 0:
        for i in query_target.child:
            add_parent(i, q)


def find_query(query_target: Query, id):
    if query_target.id == id:
        return query_target
    else:
        if len(query_target.child) > 0:
            for i in query_target.child:
                answer = find_query(i, id)
                if answer is not None:
                    return answer
        else:
            return None
    return None


def find_depth(node: Query):
    """
    find the depth of the current node
    :param node: current node
    :return: the depth of the node
    """
    node = node.parent
    if node is not None and len(node) > 0:
        for parent in node:
            return 1 + find_depth(parent)
    return 1


def analyse_ipfs_hops(cid, result_host_dic, visual=False):
    """
    analyze how many ipfs hop takes
    :param cid: cid of the object
    :param result_host_dic: a dict contains [provider : which peer responded this provider]
    :param visual: bool for visualization out put
    :return: cid and max hop the ipfs query traveled
    """
    root_query = []
    all_query = []
    all_provider = []
    all_response = []
    dht_bucket = []
    uid = 0
    with open(f'{cid}_dht.txt', 'r') as stdin:
        bucket_id = 0
        current_bucket = None
        for line in stdin.readlines():
            if "Bucket" in line:
                line = line.replace(" ", "")
                index = line.find("Bucket")
                try:
                    # deal with 2 digit id
                    bucket_id = int(line[index + 6:index + 8])
                except Exception:
                    # case of 1 digit id
                    bucket_id = int(line[index + 6:index + 7])
                current_bucket = Bucket(bucket_id)
                dht_bucket.append(current_bucket)
                continue
            elif "Peer" in line or "DHT" in line:
                continue
            else:
                # bucket reading
                line = line.split(" ")
                # case we have @ at the output
                if line[2] == "@":
                    # print(line[3])
                    current_bucket.peers.append(line[3])
                else:
                    # print(line[4])
                    if line[4] != "":
                        current_bucket.peers.append(line[4])

    with open(f'{cid}_provid.txt', 'r') as stdin:
        for line in stdin.readlines():
            if line[0] == '\t':
                continue
            line = line.replace("\n", "")
            index = line.find(": ")
            ts = line[:index]
            line = line[index + 1:]
            line = line.split(" ")
            if "querying" in line:
                cid = line[-1]
                q = Query(cid, ts, uid)
                uid += 1
                # find if parent exit or not
                for i in root_query:
                    add_parent(i, q)
                # no parent = root query
                if q.parent is None:
                    root_query.append(q)
                all_query.append(q)
            elif "says" in line:
                # case answer
                res_id = line[line.index("says") - 1]
                answer_start_index = line.index("use") + 1
                # find original query
                q = None
                for query in root_query:
                    q = find_query(query, res_id)
                    if q is not None:
                        break
                for index in range(answer_start_index, len(line)):
                    response = None
                    for r in all_response:
                        if r.id == line[index]:
                            response = r
                            break
                    if response is None:
                        response = Response(line[index], ts, uid)
                        all_response.append(response)
                        uid += 1
                    response.parent.append(q)
                    q.answer.append(response)
            elif "provider:" in line:
                provider = Provider(line[-1], ts, uid)
                uid += 1
                all_provider.append(provider)
    # case of no exist
    if len(all_provider) == 0:
        return 0
    # map provider and result record, and analyse hop info
    host_result_dic = dict(zip(result_host_dic.values(), result_host_dic.keys()))
    max_hop = 0
    for query in all_query:
        temp_hop = 0
        if query.id in host_result_dic.keys():
            temp_hop = find_depth(query)
            if temp_hop > max_hop:
                max_hop = temp_hop
    # case of visualization file output
    if visual:
        output_list = []
        level_list = root_query.copy()
        # map root to dht bucket:
        for query in root_query:
            for bucket in dht_bucket:
                if query.id in bucket.peers:
                    query.parent = [f'Bucket {bucket.id}']
                    break
        # start to analysis hop information
        root_level = True
        while len(level_list) > 0:
            temp_list = []
            temp_level_list = []
            for i in level_list:
                # update for existing node
                added = False
                for j in temp_list:
                    if j['id'] == i.id:
                        # if i.parent.id not in j['parents']:
                        j['parents'] += [x.id for x in i.parent]
                        added = True
                        break
                if added:
                    continue
                # case for new node
                peer = {'id': i.id}
                if root_level is True:
                    if i.parent is not None:
                        peer['parents'] = i.parent
                else:
                    if i.parent is not None:
                        peer['parents'] = [x.id for x in i.parent]
                temp_list.append(peer)
                if type(i) == Query:
                    if len(i.child) > 0:
                        temp_level_list += i.child
            output_list.append(temp_list)
            level_list = temp_level_list
            root_level = False

        # # read actual peer who provided answer from daemon
        # with open('daemon.txt', 'r') as stdin:
        #     result_host_dic = {}
        #     for line in stdin.readlines():
        #         if "cid" not in line:
        #             continue
        #         index = line.find("cid")
        #         line = line.replace("\n", "")
        #         line = line[index:]
        #         line = line.split(" ")
        #         result_host_dic[line[5]] = line[3]

        # map final provider to each peer
        temp_list = []
        for index in range(len(all_provider)):
            provider = all_provider[index]
            peer = {'id': f'Provider {index}',
                    # 'parents': []}
                    'parents': [result_host_dic[provider.id]]}
            temp_list.append(peer)
        output_list.append(temp_list)
        # adding bucket into output
        temp_list = []
        for bucket in dht_bucket:
            peer = {'id': f'Bucket {bucket.id}'}
            temp_list.append(peer)
        output_list.insert(0, temp_list)

        with open('visualization/node_modules/@nitaku/tangled-tree-visualization-ii/data.json', 'w') as fout:
            json.dump(output_list, fout)
    return cid, max_hop


def get_ip_hop(address: Address):
    """
    find ip hop value from given Address
    :param address: Address object
    :return: None
    """
    if address.ip_type == 'ip6' or address.protocol == 'dns':
        return
        # try to use traceroute to get rtt
    if address.protocol == 'tcp':
        protocol = "-T"
    else:
        protocol = '-U'
    # try traceroute
    process = subprocess.Popen(
        ['sudo', 'traceroute', address.ip, protocol, '-p', address.port, '-m', '100'],
        stdout=subprocess.PIPE)
    line = process.stdout.readlines()[-1]
    try:
        line = line.decode('utf-8')
        line = line.replace("\n", "")
        line = line.lstrip()
        print(line)
        address.ip_hop = line.split(" ")[0]
    except Exception:
        print(line)


def get_rtt(address: Address):
    """
    find rtt value from given Address
    :param address: Address object
    :return: None
    """
    if address.ip_type == 'ip6':
        return
    try:
        host = icmplib.ping(address.ip, count=5, interval=0.2, privileged=False)
    except Exception as e:
        print(e)
        return
    if host.is_alive:
        address.rtt = host.avg_rtt
        print(host.rtts)
    else:
        # try to use traceroute to get rtt
        process = subprocess.Popen(
            ['sudo', 'traceroute', address.ip, '-T', '-p', address.port, '-m', '100'],
            stdout=subprocess.PIPE)
        line = process.stdout.readlines()[-1]
        try:
            line = line.decode('utf-8')
            line = line.replace("\n", "")
            line = line.split(" ")
            rtt = float(line[line.index("ms") - 1])
            address.rtt = str(rtt)
        except Exception:
            print(line)


def get_peer_ip(result_host_dic: dict):
    """
    find peer multi address based on peerID
    :param result_host_dic: [provider_peerID : who provides (peerID)]
    :return: dic {provider_peerID : Address[]}
    """
    provider_ip = {}
    for peer in result_host_dic.keys():
        process = subprocess.Popen(['../ipfs', 'dht', 'findpeer', peer], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # case of no route find
        for line in process.stderr.readlines():
            if str(line) != '':
                provider_ip[peer] = []
                break

        for line in process.stdout.readlines():
            line = line.decode('utf-8')
            line = line.replace("\n", "")
            line = line.split("/")
            ip_type = line[1]
            ip_value = line[2]
            protocol = line[3]
            port = line[4]
            if ip_type == 'ip6' and ip_value == '::1':
                # local v6 ignore
                continue
            elif ip_type == 'ip4':
                # exclude private ip address
                if ipaddress.ip_address(ip_value) in ipaddress.IPv4Network('10.0.0.0/8') or \
                        ipaddress.ip_address(ip_value) in ipaddress.IPv4Network('172.16.0.0/12') or \
                        ipaddress.ip_address(ip_value) in ipaddress.IPv4Network('127.0.0.0/8') or \
                        ipaddress.ip_address(ip_value) in ipaddress.IPv4Network('192.168.0.0/16'):
                    continue
            # add valid ip address info
            if peer not in provider_ip.keys():
                provider_ip[peer] = []
            address = Address(ip_value, ip_type, port, protocol)
            provider_ip[peer].append(address)
    return provider_ip


def ips_find_provider(cid):
    """
    call ipfs to find provider for cid specified, and do a DHT dump before finding
    :param cid: cid to find
    :return: None
    """

    with open(f'{cid}_dht.txt', 'w') as stdout:
        stdout.flush()
        try:
            process = subprocess.Popen(['../ipfs', 'stats', 'dht'], stdout=stdout)
            process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()

    with open(f'{cid}_provid.txt', 'w') as stdout:
        stdout.flush()
        try:
            process = subprocess.Popen(['../ipfs', 'dht', 'findprovs', '-v', cid], stdout=stdout)
            process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()


def main(preload=False):

    today = datetime.now().date()
    all_cid = []
    # start reading all cid
    if not preload:
        with open(f'{today}_cid.txt', 'r') as stdin:
            for line in stdin.readlines():
                line = line.replace("\n", "")
                all_cid.append(line)
                ips_find_provider(line)

    # read daemon log file
    # {cid : result_host_dic={}}
    all_provider_dic = {}
    all_stats = []
    with open(f'{today}_daemon.txt', 'r') as stdin:
        for line in stdin.readlines():
            if "cid" not in line:
                continue
            index = line.find("cid")
            line = line.replace("\n", "")
            line = line[index:]
            line = line.split(" ")
            cid = line[1]
            if cid not in all_provider_dic.keys():
                result_host_dic = {}
                all_provider_dic[cid] = result_host_dic
            else:
                result_host_dic = all_provider_dic[cid]
            result_host_dic[line[5]] = line[3]
    # hop
    for cid in all_provider_dic:
        _, ipfs_hop = analyse_ipfs_hops(cid, all_provider_dic[cid])
        if ipfs_hop == 0:
            # case of no result find
            stats = Stats(cid, ipfs_hop, {})
            all_stats.append(stats)
            continue
        print(f'IPFS_HOP {ipfs_hop}')
        providers = get_peer_ip(all_provider_dic[cid])
        stats = Stats(cid, ipfs_hop, providers)
        all_stats.append(stats)
        for peer in providers.keys():
            print(peer)
            for address in providers[peer]:
                print(f'Address {address.__dict__}')
                get_rtt(address)
                get_ip_hop(address)
                print(f'Address {address.__dict__}')
    # write to file
    with open(f'{today}_summary.json', 'w') as fout:
        json.dump(all_stats, fout, cls=StatsEncoder)
    with open(f'{today}_stats.txt', 'w') as fout:
        fout.write(f"total_cid {len(all_cid)} reachable_cid {len(all_provider_dic.keys())}\n")


if __name__ == '__main__':
    preload = False
    if len(sys.argv) == 2:
        preload = True
    main(preload)
