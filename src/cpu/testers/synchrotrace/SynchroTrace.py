# Copyright (c) 2015-2016 ARM Limited
# All rights reserved.
#
# The license below extends only to copyright in the software and shall
# not be construed as granting a license to any other intellectual
# property including but not limited to intellectual property relating
# to a hardware implementation of the functionality of the software
# licensed hereunder.  You may use the software subject to the license
# terms below provided that you ensure that this notice is replicated
# unmodified and in its entirety in all distributions of the software,
# modified or unmodified, in source code or in binary form.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# Copyright (c) 2015, Drexel University All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Authors: Karthik Sangaiah
#          Ankit More
#          Radhika Jagtap
#          Mike Lui
#
# SynchroTrace is the trace replay module that plays back traces generated by
# a tool called Sigil [1]. The traces are per-thread and record not only
# compute operations and memory accesses local to the thread but also inter-
# thread communication and synchronisation primitives like locks and barriers.
# The information in the traces is architecture-agnostic. The traces are then
# replayed by the SynchroTrace model in gem5 to achieve light-weight multicore
# simulation [2].
#
# Sigil, the tool used to generate the traces is not included in gem5 but
# lives in a public repo on github [3] and has user documentation [4].
#
# References:
#
# [1] "Platform-independent analysis of function-level communication in
# workloads", Siddharth Nilakantan and Mark Hempstead, IISWC 2013.
#
# [2] "Synchrotrace: synchronization-aware architecture-agnostic traces for
# light-weight multicore simulation", Siddharth Nilakantan, Karthik Sangaiah,
# Ankit More and Giordano Salvadory, ISPASS 2015.
#
# [3] https://github.com/VANDAL/prism
#
# [4] https://vandal-prism.readthedocs.io/en/docs/
#

from m5.objects.MemObject import MemObject
from m5.params import *
from m5.proxy import *
import optparse


def addSynchrotraceOptions(parser):
    """
    SynchroTrace specific options, required regardless of memory system
    MANDATORY to set the path to the traces directory
    """
    parser.add_option("--num-threads", type="int", help="Number of threads")
    parser.add_option("--event-dir", type="string", default="",
                      help="Directory path that contains the event traces")
    parser.add_option("--output-dir", type="string", default="",
                      help="Path to the directory where to dump the output")
    parser.add_option("--start-sync-region", type="int", default=0,
                      help="Start simulation of syncronization region")
    parser.add_option("--inst-sync-region", type="int", default=0,
                      help="Select synchronization region to instrument")
    parser.add_option("--barrier-stat-dump", action="store_true",
                      default=False,
                      help="Dump stats to stats.txt following each barrier")
    parser.add_option("--monitor-freq", type="int", default=1,
                      help="Frequency at which to wake up monitor event")
    parser.add_option("--cpi-iops", type="float", default=1,
                      help="CPI for integer ops")
    parser.add_option("--cpi-flops", type="float", default=1,
                      help="CPI for floating point ops")
    parser.add_option("--pc-skip", action="store_true", default=False,
                      help="Don't enforce producer->consumer dependencies")
    parser.add_option("--memsys-clock", action="store", type="string",
                      default='1.6GHz',
                      help="Clock for Memory System")


class SynchroTraceReplayer(MemObject):
    """SynchroTrace replay model which replays multi-threaded traces generated
         by Sigil. It interfaces with the Classic Memory System or Ruby.
    """
    type = 'SynchroTraceReplayer'
    cxx_header = "cpu/testers/synchrotrace/synchro_trace.hh"
    num_cpus = Param.Int("Number of cpus / Memory Ports")
    num_threads = Param.Int("Number of threads")
    cpu_port = VectorMasterPort("Cpu ports")
    event_dir = Param.String("Location of the events profile")
    output_dir = Param.String("Directory path to dump the output")
    monitor_wakeup_freq = Param.Int(1, "How often to wakeup the master event")
    cpi_iops = Param.Float(1, "CPI for integer ops")
    cpi_flops = Param.Float(2, "CPI for floating point ops")
    pth_cycles = Param.Int(100, "Generalized pthread call cost")
    cxt_switch_cycles = Param.Int(100, "Context switch cost")
    sched_slice_cycles = Param.Int(3000, "Scheduler interval")
    ruby = Param.Bool(False,"Are we using Ruby?")
    block_size_bytes = Param.Int(64, "Cache Line Size")
    mem_size_bytes = Param.UInt64("Memory Size")
    pc_skip = Param.Bool("Skip P->C dependencies")
    start_sync_region = Param.Int("Start of synchronization region")
    inst_sync_region = Param.Int("Synchronization region to instrument")
    barrier_stat_dump = Param.Bool("Option to dump stats after barriers")
    system = Param.System(Parent.any, "System we belong to")
