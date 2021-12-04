import json
import os
import socket

import numpy as np
import matplotlib.pyplot as plt
from geolite2 import geolite2

# global plot setting
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 16
color_scheme = {'NY': 'tab:blue', 'CA': 'tab:orange', 'EU': 'tab:purple', 'JP': 'tab:red'}


def overall_cdf(data, cdf_type, x_label, save=False):
    """
    plot overall cdf for all location
    :param x_label: string for xlabel
    :param cdf_type: data source type
    :param save: true for output fig false for show only
    :param data: dic {location : {video_source : [bw data] }}
    :return:
    """
    fig, ax = plt.subplots()
    for location, video_source_data in data.items():
        for video_source, x_data in video_source_data.items():
            y_data = np.arange(len(x_data)) / float(len(x_data))
            if 'public' in video_source:
                ax.plot(x_data, y_data, '--', label=f'{location} {video_source}', color=color_scheme[location])
            else:
                ax.plot(x_data, y_data, label=f'{location} {video_source}', color=color_scheme[location])
    ax.set_title(f'Video Overall {cdf_type} CDF')
    ax.set_xlabel(x_label)
    ax.set_ylabel('CDF')
    if cdf_type == 'Connection Time':
        plt.xlim(0, 60)
        ax.plot([4, 4], [0, 1], '--', color='green')
    plt.ylim(0, 1)
    ax.legend()
    if save:
        plt.savefig(f'Video_{cdf_type}_CDF.png')
    plt.show()


def continues_graph(data, source, y_label, save=False):
    """
    plot a longest local reachable vid and compare the bw for local gateway and public gateway
    :param y_label: y label text
    :param source: data type needs to graph
    :param save: true for output fig false for show only
    :param data: daily record for all location = dic { location {date : [vid_info]}}
    :return: None
    """
    vid_data = {}
    for location, date_data in data.items():
        if location not in vid_data:
            vid_data[location] = {}
        # get first day data
        first_date = list(date_data.keys())[0]
        first_date_data = date_data[first_date]
        # find all cid with local data
        local_reachable_cids = []
        for vid in first_date_data:
            if vid['local_data'] is not None:
                local_reachable_cids.append(vid['cid'])
        # trace everyday
        for date, daily_data in date_data.items():
            daily_temp_data = {}
            daily_temp_local = []
            daily_temp_public = []
            daily_temp_rest = []
            for vid in daily_data:
                if vid['cid'] in local_reachable_cids and vid['local_data'] is not None:
                    # print(f'{location} {date} {vid["cid"]}')
                    if source == 'Bandwidth':
                        daily_temp_local.append(float(vid['local_data']['bandwidth']) / (1024 * 1024))
                        daily_temp_public.append(float(vid['public_data']['bandwidth']) / (1024 * 1024))
                    elif source == 'Connection Time':
                        daily_temp_local.append(float(vid['local_data']['overhead']))
                        daily_temp_public.append(float(vid['public_data']['overhead']))
                elif vid['public_data'] is not None:
                    if source == 'Bandwidth':
                        daily_temp_rest.append(float(vid['public_data']['bandwidth']) / (1024 * 1024))
                    elif source == 'Connection Time':
                        daily_temp_rest.append(float(vid['public_data']['overhead']))
            if len(daily_temp_local) > 0:
                daily_temp_data['local'] = np.mean(daily_temp_local)
            else:
                daily_temp_data['local'] = float('nan')
            if len(daily_temp_public) > 0:
                daily_temp_data['public'] = np.mean(daily_temp_public)
            else:
                daily_temp_data['public'] = float('nan')
            daily_temp_data['rest'] = np.mean(daily_temp_rest)
            vid_data[location][date] = daily_temp_data
    # plot graph
    fig, ax = plt.subplots(figsize=(11, 10))
    x_data = list(data['NY'].keys())
    x_data.sort()
    public_compare_data = {}
    for location, video_source_data in vid_data.items():
        y_local_data = []
        y_public_data = []
        y_public_rest_data = []
        for date in x_data:
            if date in vid_data[location].keys():
                y_local_data.append(vid_data[location][date]['local'])
                y_public_data.append(vid_data[location][date]['public'])
                y_public_rest_data.append(vid_data[location][date]['rest'])
            else:
                y_local_data.append(float('nan'))
                y_public_data.append(float('nan'))
                y_public_rest_data.append(float('nan'))
        public_compare_data[location] = {'public': y_public_data, 'rest': y_public_rest_data}
        ax.plot(x_data, y_local_data, '*-', label=f'{location}_local_gateway', color=color_scheme[location])
        ax.plot(x_data, y_public_data, '--', label=f'{location}_public_gateway', color=color_scheme[location])
    ax.set_title(f'Average {source} for Local Reachable Videos Over Time\n\n\n')
    ax.set_xlabel('Date')
    ax.set_ylabel(y_label)
    ax.legend(bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left",
              mode="expand", borderaxespad=0, ncol=3)
    ax.tick_params(axis='x', labelrotation=70)
    if save:
        plt.savefig(f'{source}_Local_VS_Public.png')
    plt.show()

    # plot public reachable bw vs non local reachable bw
    fig, ax = plt.subplots(figsize=(12, 11))
    for location, y_data in public_compare_data.items():
        ax.plot(x_data, y_data['public'], '^-', label=f'{location} local reachable ', color=color_scheme[location])
        ax.plot(x_data, y_data['rest'], '--', label=f'{location} local non-reachable ', color=color_scheme[location])
    ax.set_title(f'Average {source} for Public Gateway Videos Over Time\n\n\n\n')
    ax.set_xlabel('Date')
    ax.set_ylabel(y_label)
    ax.legend(bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left",
              mode="expand", borderaxespad=0, ncol=2)
    ax.tick_params(axis='x', labelrotation=70)
    if save:
        plt.savefig(f'{source}_Public_VS_Public.png')
    plt.show()


def cdf_graph(data, cdf_type, x_label, save=False):
    """
    plot total video duration cdf
    :param x_label: label text for x axis
    :param cdf_type: cdf data source
    :param save: true for output fig false for show only
    :param data: dic {location : [duration array]}
    :return: None
    """
    fig, ax = plt.subplots()
    for location, x_data in data.items():
        y_data = np.arange(len(x_data)) / float(len(x_data))
        ax.plot(x_data, y_data, label=f'{location}', color=color_scheme[location])
    ax.set_title(f'{cdf_type} CDF')
    ax.set_xlabel(f'{x_label}')
    ax.set_ylabel('CDF')
    ax.legend()
    if save:
        plt.savefig(f'{cdf_type}_CDF.png')
    plt.show()


def summary_graph(data, save=False):
    """
    plot summary data
    :param save: true for output fig false for show only
    :param data: dic {date : summary data}
    :return: None
    """
    # x = date
    x_data = []
    y_data = {}
    for date, summary_data in data.items():
        x_data.append(date)
        for vid_type, vid_data in summary_data.items():
            for vid_source, vid_count in vid_data.items():
                if vid_source == 'total_video':
                    continue
                data_name = f'{vid_type}_{vid_source}'
                if data_name not in y_data:
                    y_data[data_name] = []
                y_data[data_name].append(vid_count)
    fig, ax = plt.subplots(figsize=(11, 10))
    for label, y in y_data.items():
        ax.plot(x_data, y, '*-', label=label)
    ax.set_title('Dtube Daily Video Distribution\n\n\n')
    ax.legend(bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left",
              mode="expand", borderaxespad=0, ncol=3)
    ax.tick_params(axis='x', labelrotation=70)
    ax.set_xlabel('Date')
    ax.set_ylabel('Video Count')
    if save:
        plt.savefig('Video_Distribution_Summary.png')
    plt.show()


def daily_ratio_graph(data, save=False):
    """
    ploy daily ipfs reachable video vs non reachable
    :param save: true for output fig false for show only
    :param data: dic {location : {date : local vs public count}}
    :return: None
    """
    fig, ax = plt.subplots(figsize=(10, 9))
    x_data = data['NY'].keys()
    for location, daily_data in data.items():
        y_local_data = []
        y_public_data = []
        for date in x_data:
            if date in daily_data:
                y_local_data.append(daily_data[date]['local'])
                y_public_data.append(daily_data[date]['public'])
            else:
                y_local_data.append(float('nan'))
                y_public_data.append(float('nan'))
        ax.plot(x_data, y_local_data, label=f'{location}_local', color=color_scheme[location])
        ax.plot(x_data, y_public_data, '--', label=f'{location}_public', color=color_scheme[location])
    ax.tick_params(axis='x', labelrotation=70)
    ax.set_title('Local Reachable Video VS. Public Reachable Video')
    ax.set_xlabel('Date')
    ax.set_ylabel('Video Count')
    ax.legend()
    if save:
        plt.savefig('Video_Ratio.png')
    plt.show()


def main():
    save_file = True
    # trace though dir
    directory = ['NY', 'CA', 'EU', 'JP']
    #  dic : {date : data}
    summary_dic = {'NY': {}, 'CA': {}, 'EU': {}, 'JP': {}}
    daily_dic = {'NY': {}, 'CA': {}, 'EU': {}, 'JP': {}}
    all_vid_dic = {'NY': {}, 'CA': {}, 'EU': {}, 'JP': {}}
    hop_dic = {'NY': {}, 'CA': {}, 'EU': {}, 'JP': {}}
    for path in directory:
        for _, _, files in os.walk(path):
            files.sort()
            for file in files:
                # load summary json
                if "hop_summary" in file:
                    # case of hop information
                    with open(f'{path}/{file}') as fin:
                        all_hop_data = json.load(fin)
                    hop_dic[path] = all_hop_data
                elif "summary" in file and "all_vid" not in file:
                    index = file.find("summary")
                    date = file[:index - 1]
                    # print(f'Summary {date}')
                    with open(f'{path}/{file}') as fin:
                        summary_data = json.load(fin)
                    summary_dic[path][date] = summary_data
                elif "all_vid" in file:
                    # case of full data
                    with open(f'{path}/{file}') as fin:
                        all_vid_data = json.load(fin)
                    all_vid_dic[path] = all_vid_data
                elif 'zip' not in file:
                    # daily data
                    index = file.find('.')
                    date = file[:index]
                    # print(f'Daily {date}')
                    with open(f'{path}/{file}') as fin:
                        daily_data = json.load(fin)
                    daily_dic[path][date] = daily_data
    # plot summary
    summary_graph(summary_dic['NY'], save=save_file)
    # plot duration cdf
    duration_data = {}
    for location, all_vid_info in all_vid_dic.items():
        if location not in duration_data:
            duration_data[location] = []
        for _, vid_info in all_vid_info.items():
            duration_data[location].append(float(vid_info['dur']) / 60)
        duration_data[location].sort()
    cdf_graph(duration_data, 'Video Duration', 'Duration (Min)', save=save_file)
    # plot overall cdf
    overall_bw_data = {}
    overall_overhead_data = {}
    video_ratio_data = {}
    for location, date_data in daily_dic.items():
        if location not in overall_bw_data:
            overall_bw_data[location] = {'local_gateway': [], 'public_gateway': []}
        if location not in overall_overhead_data:
            overall_overhead_data[location] = {'local_gateway': [], 'public_gateway': []}
        if location not in video_ratio_data:
            video_ratio_data[location] = {}
        for date, daily_data in date_data.items():
            video_ratio_data[location][date] = {'local': 0, 'public': 0}
            for vid in daily_data:
                if vid['local_data'] is not None:
                    overall_bw_data[location]['local_gateway'].append(
                        float(vid['local_data']['bandwidth']) / (1024 * 1024))
                    overall_overhead_data[location]['local_gateway'].append(
                        float(vid['local_data']['overhead']))
                    video_ratio_data[location][date]['local'] += 1
                if vid['public_data'] is not None:
                    overall_bw_data[location]['public_gateway'].append(
                        float(vid['public_data']['bandwidth']) / (1024 * 1024))
                    overall_overhead_data[location]['public_gateway'].append(
                        float(vid['public_data']['overhead']))
                    video_ratio_data[location][date]['public'] += 1
        overall_bw_data[location]['local_gateway'].sort()
        overall_bw_data[location]['public_gateway'].sort()
        overall_overhead_data[location]['local_gateway'].sort()
        overall_overhead_data[location]['public_gateway'].sort()
    # plot overall cdf
    overall_cdf(overall_bw_data, 'Bandwidth', 'Bandwidth (Mbps)', save=save_file)
    overall_cdf(overall_overhead_data, 'Connection Time', 'Connection Time (s)', save=save_file)
    # plot specific video bw and connection time
    continues_graph(daily_dic, 'Bandwidth', 'Bandwidth (Mbps)', save=save_file)
    continues_graph(daily_dic, 'Connection Time', 'Connection Time (s)', save=save_file)
    # plot daily ratio graph
    daily_ratio_graph(video_ratio_data, save=save_file)
    # analysis ip info
    provider_data = {}
    rtt_data = {}
    ip_data = {}
    for location, ip_info in hop_dic.items():
        print(f'{location} {len(ip_info)}')
        provider_data[location] = []
        rtt_data[location] = []
        ip_data[location] = []
        for ip in ip_info:
            providers = ip['providers']
            provider_data[location].append(len(providers.keys()))
            for _, addresses in providers.items():
                for address in addresses:
                    ip_address = address['ip']
                    if ip_address not in ip_data[location]:
                        ip_data[location].append(ip_address)
                        rtt = address['rtt']
                        if rtt is not None:
                            rtt_data[location].append(float(rtt))
        provider_data[location].sort()
        rtt_data[location].sort()
    # provider CDF
    cdf_graph(provider_data, 'Provider Count', 'Provider ID Count', save=save_file)
    # plot RTT CDF
    cdf_graph(rtt_data, 'Provider RTT', 'RTT (ms)', save=save_file)
    # plot GEO?
    geo = geolite2.reader()
    ip_geo = {}
    for location, ip_address in ip_data.items():
        ip_geo[location] = {}
        for ip in ip_address:
            try:
                x = geo.get(ip)
                if 'country' in x.keys():
                    country = x['country']['names']['en']
                elif 'registered_country' in x.keys():
                    country = x['registered_country']['names']['en']
                else:
                    print(x)
                    continue
                if country not in ip_geo[location]:
                    ip_geo[location][country] = 0
                ip_geo[location][country] += 1
            except Exception as e:
                # try resolve ip from domain
                try:
                    ip_value = socket.gethostbyname(ip)
                    x = geo.get(ip_value)
                    if 'country' in x.keys():
                        country = x['country']['names']['en']
                    elif 'registered_country' in x.keys():
                        country = x['registered_country']['names']['en']
                    else:
                        print(x)
                        continue
                    print(country)
                    if country not in ip_geo[location]:
                        ip_geo[location][country] = 0
                    ip_geo[location][country] += 1
                except Exception as e:
                    print(e)
    print(ip_geo)


if __name__ == '__main__':
    main()
