#=
Tek-algoritma / tek-instance surucu (HLBB kiyasi icin).
Kullanim:
  julia run_one.jl <ALGO> <instance.txt> <wall_seconds> [seed]
ALGO: SA GA MSA HGA FSS VNS ALNS FACL GALA HABC SSAFA WOAFA
Cikti (stdout son satir):  RESULT <ALGO> <makespan> <iters> <evals> <wall_s>

Vallada .txt formati okunur (dataset_vallada/large/I_n_m_S_..._r.txt). Eligibility YOK (saf).
Zaman butcesi: her algoritma dahili t/2000*n*m sn kullanir -> wall_seconds'e esitlemek icin
t = round(wall_seconds*2000/(n*m)). Boylece TUM algoritmalar ayni wall-clock alir (HLBB=300s ile adil).
=#

include("Modules.jl")
using .ALNS, .FACL, .FSS, .GA, .GALA, .HABC, .HGA, .MSA, .SA, .SSAFA, .VNSaiNet, .WOAFA
using Random

function parse_vallada(path::String)
    lines = String[]
    for ln in eachline(path)
        s = strip(replace(ln, "\r" => ""))
        if s != ""
            push!(lines, s)
        end
    end
    hdr = split(lines[1])
    n = parse(Int, hdr[1]); m = parse(Int, hdr[2])
    # satir 2 = nMachine (atla). is-satirlari: lines[3..3+n-1]
    p = zeros(Int16, m, n)
    for i in 1:n
        toks = split(lines[2+i])
        # format: mach0 p0 mach1 p1 ...  (cift indeksli token = proc)
        for j in 1:2:length(toks)
            mach = parse(Int, toks[j]) + 1   # 0-index -> 1-index
            proc = parse(Int, toks[j+1])
            p[mach, i] = proc
        end
    end
    # "SSD" satirini bul
    ssd = findfirst(x -> x == "SSD", lines)
    S = Matrix{Int16}[]
    cur = ssd + 1
    for k in 1:m
        # "M{k-1}" basligi
        @assert startswith(lines[cur], "M") "beklenen M-baslik, bulunan: $(lines[cur])"
        cur += 1
        MSDST = zeros(Int16, n, n)
        for r in 1:n
            toks = split(lines[cur])
            for c in 1:n
                MSDST[r, c] = parse(Int, toks[c])
            end
            cur += 1
        end
        push!(S, MSDST)
    end
    return n, m, p, S
end

function parse_niche_bin(path::String)
    #= Nis binary (niche_bridge.py uretir; Julia'da JSON.jl yok -> paketsiz kopru).
       Duzen: n,m:Int32 | ready:Int32[m] | elig:Int8[m,n] | proc:Int32[m,n] | setup:Int32[n,n] x m =#
    io = open(path, "r")
    n = Int(read(io, Int32)); m = Int(read(io, Int32))
    ready = Array{Int32}(undef, m);    read!(io, ready)
    E     = Array{Int8}(undef, m, n);  read!(io, E)      # E[machine, job]
    P     = Array{Int32}(undef, m, n); read!(io, P)      # P[machine, job]
    S = Matrix{Int16}[]
    for l in 1:m
        A = Array{Int32}(undef, n, n); read!(io, A)      # A[i,j] = i->j hazirlik
        push!(S, Int16.(A))
    end
    close(io)
    p = Int16.(P)
    Mel = [[Int(E[l, j]) for l in 1:m] for j in 1:n]     # _set_niche! format: M[job][machine]
    rdy = [Int(ready[l]) for l in 1:m]
    return n, m, p, S, rdy, Mel
end

function main()
    algo = ARGS[1]
    path = ARGS[2]
    wall = parse(Float64, ARGS[3])
    seed = length(ARGS) >= 4 ? parse(Int, ARGS[4]) : 0

    #----- .nbin => NIS modu (ready + eligibility); .txt => saf Vallada (eski yol, degismedi)
    niche = endswith(path, ".nbin")
    rdy = Int[]; Mel = Vector{Vector{Int}}()
    if niche
        n, m, p, S, rdy, Mel = parse_niche_bin(path)
        if !(algo in ("SA", "HGA", "GA"))
            error("nis modu yalnizca nise-genisletilmis algoritmalar icin: SA/HGA/GA (verilen: $algo)")
        end
    else
        n, m, p, S = parse_vallada(path)
    end
    t = max(1, round(Int, wall * 2000.0 / (n * m)))
    Random.seed!(seed)

    mI = Int8(m); nI = Int16(n)
    t0 = time()
    r = if niche
        #----- nis: r=/M= ile eligibility+ready aktive
        if algo == "SA";       Main_SA(mI, nI, p, S, t; r = rdy, M = Mel)
        elseif algo == "HGA";  Main_HGA(mI, nI, p, S, t; r = rdy, M = Mel)
        else;                  Main_GA(mI, nI, p, S, t; r = rdy, M = Mel)
        end
    elseif algo == "SA";    Main_SA(mI, nI, p, S, t)
    elseif algo == "GA";    Main_GA(mI, nI, p, S, t)
    elseif algo == "MSA";   Main_MSA(mI, nI, p, S, t)
    elseif algo == "HGA";   Main_HGA(mI, nI, p, S, t)
    elseif algo == "FSS";   Main_FSS(mI, nI, p, S, t)
    elseif algo == "VNS";   Main_VNS(mI, nI, p, S, t)
    elseif algo == "ALNS";  Main_ALNS(mI, nI, p, S, t)
    elseif algo == "FACL";  Main_FACL(mI, nI, p, S, t)
    elseif algo == "GALA";  Main_GALA(mI, nI, p, S, t)
    elseif algo == "HABC";  Main_HABC(mI, nI, p, S, t)
    elseif algo == "SSAFA"; Main_SSAFA(mI, nI, p, S, t)
    elseif algo == "WOAFA"; Main_WOAFA(mI, nI, p, S, t)
    else error("bilinmeyen algoritma: $algo")
    end
    wall_real = time() - t0
    OF, I, NI = r[1], r[2], r[3]
    tbest = length(r) >= 4 ? round(r[4], digits=1) : -1.0   # -1 when not instrumented
    # internal budget = n*m*t/2000 s (wall clock pinned to budget; written out for verification)
    tlim = round(n * m * t / 2000.0, digits=1)
    println("RESULT $algo $OF $I $NI $(round(wall_real, digits=1)) $tbest $tlim")
    # [DIS-DENETIM] cizelge de dondurulduyse (r[5]) SOL satirina bas: Python tarafi
    # feasibility.py ile denetlesin. Bicim: makineler '|' ile, isler ',' ile, 1-INDEKSLI
    # (Python 0-indekse cevirir). Cizelge dondurmeyen yontemlerde satir hic basilmaz.
    if length(r) >= 5 && r[5] !== nothing
        sol = r[5]
        println("SOL " * join([join(string.(Int.(sol[l])), ",") for l in 1:Int(m)], "|"))
    end
end

# yalnizca dogrudan calistirilinca kos (test'ten include edilince main tetiklenmesin)
if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
