#=
* Implementation of the Simulated Annealing with Stochastic Local Search (SA) of Santos et al.
* International Transactions in Operational Research 00 (2016) 1–18
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
* NIS GENISLETMESI (HLBB): eligibility M_j + ready-time r_l eklendi. TUM eklemeler PURE-MODDA
  NO-OP -> _niche_pure=true iken guard'lar tetiklenmez, RNG-akisi pure SA ile BIREBIR ayni
  (equivalence testi dogrular). Main_SA'da _set_niche! ile aktive edilir.
=#

# ================= NIS KATMANI (elig M_j + ready r_l) =================
_READY = Int32[]                 # r_l (pure: zeros(m))
_ELIG = Vector{Bool}[]           # _ELIG[job][mach] (pure: bos, kullanilmaz)
_niche_pure = true               # true -> elig guard'lari no-op

function _set_niche!(m::Int, n::Int, r, M)
    global _READY, _ELIG, _niche_pure
    _READY = Int32[Int32(r === nothing ? 0 : r[l]) for l in 1:m]
    _niche_pure = (M === nothing)
    _ELIG = _niche_pure ? Vector{Bool}[] :
            Vector{Bool}[Bool[M[j][l] == 1 for l in 1:m] for j in 1:n]
end

@inline _ok(job::Integer, mach::Integer) = _niche_pure || _ELIG[job][mach]   # pure: hep true
# =====================================================================

function MachineSpan(mach::Int8, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, sol::Vector{Vector{Int16}})
    #----- Calculates and returns the makespan of the solution

    span::Int32 = _READY[mach]    # NIS: ready-time r_l (pure: 0)
    size::Int16 = length(sol[mach])

    for i in eachindex(sol[mach])
        if i != size
            span += p[mach, sol[mach][i]] + S[mach][sol[mach][i], sol[mach][i+1]]
        else
            span += p[mach, sol[mach][i]]
        end
    end
    
    return(span)
end

function InitialSolution(m::Int8, n::Int16)
    #----- Generates the initial solution

    U = collect(Int16, 1:n) # Unscheduled jobs
    sol = Vector{Int16}[[] for i in 1:m] # Initial solution
    C::Int16 = length(U)

    while C != 0
        r = rand(1:m)
        while !_ok(U[1], r); r = rand(1:m); end   # NICHE: eligible machine (pure: no-op)
        push!(sol[r], U[1])
        popfirst!(U)
        C -= 1
    end
    
    return(sol)
end

function MachineSelection(m::Int8, MS::Vector{Int32})
    #----- Selects the machine to be evaluated

    SMM = rand(Bool) # Selection of makespan machine
    Mx::Int8 = 0 # Index of selected machine
    
    if SMM == true
        Mx = argmax(MS)
    else
        Mx = rand(1:m)
    end
    
    return(Mx)
end

function Shift(m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    sol::Vector{Vector{Int16}}, MS::Vector{Int32})
    #----- Shifts a random job to another position in the same machine

    Mx::Int8 = MachineSelection(m, MS)
    size::Int16 = length(sol[Mx])
    NI::Int64 = 0

    while size <= 1 
        Mx = MachineSelection(m, MS)
        size = length(sol[Mx])
    end

    INT = rand(Bool)

    if INT == true
        pos::Int16 = rand(1:size)
        job::Int16 = sol[Mx][pos]
        deleteat!(sol[Mx], pos)
        best_span::Int32 = 999999
        best_pos::Int16 = 0

        for i in 1:size 
            insert!(sol[Mx], i, job)
            span::Int32 = MachineSpan(Mx, p, S, sol)
            NI += 1

            if span < best_span 
                best_span = span
                best_pos = i
            end

            deleteat!(sol[Mx], i)
        end

        insert!(sol[Mx], best_pos, job)
        MS[Mx] = best_span
    else
        pos = rand(1:size)
        job = sol[Mx][pos]
        deleteat!(sol[Mx], pos)

        ins_pos::Int16 = rand(1:size)

        if ins_pos == pos 
            while ins_pos == pos
                ins_pos = rand(1:size)
            end
        end

        insert!(sol[Mx], ins_pos, job)
        MS[Mx] = MachineSpan(Mx, p, S, sol)
        NI += 1
    end

    return(NI)
end

function Switch(m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    sol::Vector{Vector{Int16}}, MS::Vector{Int32})
    #----- Switches the positions of two selected jobs on the same machine 

    Mx::Int8 = MachineSelection(m, MS)
    size::Int16 = length(sol[Mx])
    NI::Int64 = 0

    while size <= 1
        Mx = MachineSelection(m, MS)
        size = length(sol[Mx])
    end

    INT = rand(Bool)

    if INT == true 
        pos::Int16 = rand(1:size)
        job1::Int16 = sol[Mx][pos]
        best_span::Int32 = 999999
        best_pos::Int16 = 0

        for i in eachindex(sol[Mx])
            if sol[Mx][i] != job1
                job2::Int16 = sol[Mx][i]

                sol[Mx][i] = job1
                sol[Mx][pos] = job2

                span::Int32 = MachineSpan(Mx, p, S, sol)
                NI += 1

                if span < best_span 
                    best_span = span
                    best_pos = i 
                end

                sol[Mx][i] = job2
                sol[Mx][pos] = job1
            end
        end

        best_job::Int16 = sol[Mx][best_pos]
        sol[Mx][best_pos] = job1
        sol[Mx][pos] = best_job
        MS[Mx] = best_span
    else
        pos = rand(1:size)
        job1 = sol[Mx][pos]
        pos2::Int16 = rand(1:size)

        while pos2 == pos 
            pos2 = rand(1:size)
        end

        job2 = sol[Mx][pos2]

        sol[Mx][pos] = job2
        sol[Mx][pos2] = job1
        MS[Mx] = MachineSpan(Mx, p, S, sol)
        NI += 1
    end

    return(NI)
end

function TaskMove(m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    sol::Vector{Vector{Int16}}, MS::Vector{Int32})
    #----- Move a job from a source machine to a target machine

    Mx::Int8 = MachineSelection(m, MS)
    size::Int16 = length(sol[Mx])
    NI::Int64 = 0 

    #----- This neighborhood requires that the target machine has at least one job

    while size == 0 
        Mx = MachineSelection(m, MS)
        size = length(sol[Mx])
    end

    INT = rand(Bool)
    
    if INT == true 
        My::Int8 = rand(1:m)

        while Mx == My 
            My = rand(1:m)
        end

        pos::Int16 = rand(1:size)
        job::Int16 = sol[Mx][pos]
        # NICHE: pick target My eligible for the job (pure: no-op). No eligible target: cancel the move (nothing mutated yet).
        trA::Int16 = 0
        while !_ok(job, My) && trA < 3*m; My = rand(1:m); while My == Mx; My = rand(1:m); end; trA += 1; end
        if !_ok(job, My); return(NI); end
        best_span::Int32= 999999
        best_pos::Int16 = 0
        last::Int16 = length(sol[My])+1

        deleteat!(sol[Mx], pos)
        MS[Mx] = MachineSpan(Mx, p, S, sol)
        NI += 1

        for i::Int16 in 1:last
            insert!(sol[My], i, job)
            span::Int32 = MachineSpan(My, p, S, sol)
            NI += 1

            if span < best_span
                best_span = span 
                best_pos = i
            end

            deleteat!(sol[My], i)
        end

        insert!(sol[My], best_pos, job)
        MS[My] = best_span
    else
        My = rand(1:m)

        while My == Mx
            My = rand(1:m)
        end

        pos = rand(1:size)
        job = sol[Mx][pos]
        trB::Int16 = 0                                # NIS (pure: no-op)
        while !_ok(job, My) && trB < 3*m; My = rand(1:m); while My == Mx; My = rand(1:m); end; trB += 1; end
        if !_ok(job, My); return(NI); end
        last = length(sol[My])+1
        ins_pos::Int16 = rand(1:last)

        deleteat!(sol[Mx], pos)
        MS[Mx] = MachineSpan(Mx, p, S, sol)
        NI += 1
        insert!(sol[My], ins_pos, job)
        MS[My] = MachineSpan(My, p, S, sol)
        NI += 1
    end
    
    return(NI)
end

function InsertBestPos(sol::Vector{Vector{Int16}}, job::Int16, ins_m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Inserts a removed job on the best position of a target machine

    best_span::Int32 = 999999999 
    best_pos::Int16 = 0
    last::Int16 = length(sol[ins_m])+1

    for i in 1:last
        insert!(sol[ins_m], i, job)
        span::Int32 = MachineSpan(ins_m, p, S, sol)

        if span < best_span
            best_span = span
            best_pos = i
        end

        deleteat!(sol[ins_m], i)
    end

    insert!(sol[ins_m], best_pos, job)
    
    return(best_span)
end

function Swap(m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    sol::Vector{Vector{Int16}}, MS::Vector{Int32})
    #----- Swap two random jobs from two different MachineSelection

    Mx::Int8 = MachineSelection(m, MS)
    NI::Int64 = 0

    while length(sol[Mx]) == 0
        Mx = MachineSelection(m, MS)
    end

    if length(sol[Mx]) == n 
        return(NI)
    end

    INT = rand(Bool)

    if INT == true
        My::Int8 = rand(1:m)

        while My == Mx || length(sol[My]) == 0
            My = rand(1:m)
        end

        #----- Randomly selects and removes the first job

        pos::Int16 = rand(1:length(sol[Mx]))
        job1::Int16 = sol[Mx][pos]
        pos_b::Int16 = rand(1:length(sol[My]))       # RNG order: pos(Mx) then pos(My) -- the deletion consumes no RNG draw
        job2::Int16 = sol[My][pos_b]
        # NIS: uygun CIFT bulana kadar yeniden cek -- TaskMove:230 ile AYNI desen ve ayni
        # sinir (3*m). Pure'da _ok hep true -> dongu hic donmez, RNG tuketilmez, equivalence korunur.
        trS::Int16 = 0
        while !(_ok(job1, My) && _ok(job2, Mx)) && trS < 3*m
            pos = rand(1:length(sol[Mx])); job1 = sol[Mx][pos]
            pos_b = rand(1:length(sol[My])); job2 = sol[My][pos_b]
            trS += 1
        end
        if !(_ok(job1, My) && _ok(job2, Mx)); return(NI); end   # uygun cift yok -> iptal
        deleteat!(sol[Mx], pos)
        deleteat!(sol[My], pos_b)

        #----- Inserts the job in the best position of the other machine

        MS[My] = InsertBestPos(sol, job1, My, p, S)
        MS[Mx] = InsertBestPos(sol, job2, Mx, p, S)
    else
        My = rand(1:m)

        while My == Mx || length(sol[My]) == 0
            My = rand(1:m)
        end

        size1::Int16 = length(sol[Mx])
        size2::Int16 = length(sol[My])

        #----- Randomly selects and removes the first job

        pos = rand(1:size1)
        job1 = sol[Mx][pos]
        pos_c::Int16 = rand(1:size2)                 # RNG: pos(Mx) then pos(My)
        job2 = sol[My][pos_c]
        trS2::Int16 = 0                                          # NIS: bkz. yukaridaki desen
        while !(_ok(job2, Mx) && _ok(job1, My)) && trS2 < 3*m
            pos = rand(1:size1); job1 = sol[Mx][pos]
            pos_c = rand(1:size2); job2 = sol[My][pos_c]
            trS2 += 1
        end
        if !(_ok(job2, Mx) && _ok(job1, My)); return(NI); end   # uygun cift yok -> iptal
        deleteat!(sol[Mx], pos)
        deleteat!(sol[My], pos_c)

        #----- Inserts the jobs in random positions

        ins_pos1::Int16 = rand(1:size1)
        ins_pos2::Int16 = rand(1:size2)

        insert!(sol[Mx], ins_pos1, job2)
        MS[Mx] = MachineSpan(Mx, p, S, sol)
        NI += 1
        insert!(sol[My], ins_pos2, job1)
        MS[My] = MachineSpan(My, p, S, sol)
        NI += 1
    end

    return(NI)
end

function TwoShift(m::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    sol::Vector{Vector{Int16}}, MS::Vector{Int32})
    #----- Apply the shift procedure twice

    Mx::Int8 = MachineSelection(m, MS)
    INT = rand(Bool)
    size::Int16 = length(sol[Mx])
    NI::Int64 = 0

    while size <= 1
        Mx = MachineSelection(m, MS)
        size = length(sol[Mx])
    end

    if INT == true
        for x::Int8 in 1:2
            pos::Int16 = rand(1:size)
            job::Int16 = sol[Mx][pos]
            deleteat!(sol[Mx], pos)
            best_span::Int32 = 999999
            best_pos::Int16 = 0
    
            for i in 1:size 
                insert!(sol[Mx], i, job)
                span::Int32 = MachineSpan(Mx, p, S, sol)
                NI += 1
    
                if span < best_span 
                    best_span = span
                    best_pos = i
                end
    
                deleteat!(sol[Mx], i)
            end
    
            insert!(sol[Mx], best_pos, job)
            MS[Mx] = best_span
        end
    else
        for x::Int8 in 1:2
            pos = rand(1:size)
            job = sol[Mx][pos]
            deleteat!(sol[Mx], pos)
            ins_pos::Int16 = rand(1:size)
        
            if ins_pos == pos 
                while ins_pos == pos
                    ins_pos = rand(1:size)
                end
            end
        
            insert!(sol[Mx], ins_pos, job)
            MS[Mx] = MachineSpan(Mx, p, S, sol)
            NI += 1
        end
    end

    return(NI)
end

function DirectSwap(m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    sol::Vector{Vector{Int16}}, MS::Vector{Int32})
    #----- Selects two jobs from different machines and swaps them

    Mx::Int8 = MachineSelection(m, MS)
    NI::Int64 = 0

    while length(sol[Mx]) == 0 
        Mx = MachineSelection(m, MS)
    end

    if length(sol[Mx]) == n 
        return(NI)
    end

    INT = rand(Bool)

    if INT == true
        My::Int8 = rand(1:m)

        while My == Mx || length(sol[My]) == 0
            My = rand(1:m)
        end

        #----- Randomly selects and removes the first job

        pos::Int16 = rand(1:length(sol[My]))
        job::Int16 = sol[My][pos]
        trD::Int16 = 0                                           # NIS: bkz. Swap'teki desen
        while !_ok(job, Mx) && trD < 3*m
            pos = rand(1:length(sol[My])); job = sol[My][pos]; trD += 1
        end
        if !_ok(job, Mx); return(NI); end   # uygun is yok -> iptal
        best_span::Int32 = 999999
        best_pos::Int16 = 0

        #----- Find the best job and perform the swap

        for i::Int16 in eachindex(sol[Mx])
            cjob::Int16 = sol[Mx][i]
            if !_ok(cjob, My); continue; end   # NIS: cjob My'ye gidecek (pure: no-op)
            sol[Mx][i] = job
            span = MachineSpan(Mx, p, S, sol)
            NI += 1

            if span < best_span
                best_span = span 
                best_pos = i 
            end

            sol[Mx][i] = cjob
        end

        if best_pos == 0; return(NI); end   # NIS: uygun cjob yok (pure: no-op)
        sjob::Int16 = sol[Mx][best_pos]
        sol[Mx][best_pos] = job
        sol[My][pos] = sjob
        MS[Mx] = best_span
        MS[My] = MachineSpan(My, p, S, sol)
        NI += 1
    else
        My = rand(1:m)

        while My == Mx || length(sol[My]) == 0
            My = rand(1:m)
        end

        pos1::Int16 = rand(1:length(sol[Mx]))
        job1::Int16 = sol[Mx][pos1]
        pos2::Int16 = rand(1:length(sol[My]))
        job2::Int16 = sol[My][pos2]
        trD2::Int16 = 0                                          # NIS: bkz. Swap'teki desen
        while !(_ok(job2, Mx) && _ok(job1, My)) && trD2 < 3*m
            pos1 = rand(1:length(sol[Mx])); job1 = sol[Mx][pos1]
            pos2 = rand(1:length(sol[My])); job2 = sol[My][pos2]
            trD2 += 1
        end
        if !(_ok(job2, Mx) && _ok(job1, My)); return(NI); end   # uygun cift yok -> iptal

        sol[Mx][pos1] = job2
        sol[My][pos2] = job1

        MS[Mx] = MachineSpan(Mx, p, S, sol)
        NI += 1
        MS[My] = MachineSpan(My, p, S, sol)
        NI += 1
    end

    return(NI)
end

function LocalSearch(sol::Vector{Vector{Int16}}, MS::Vector{Int32},
    m::Int8, n::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Selects the neighborhood to be explored

    NEI::Int8 = rand(1:6)
    NI::Int64 = 0 

    if NEI == 1 
        NI += Shift(m, p, S, sol, MS)
    elseif NEI == 2
        NI += Switch(m, p, S, sol, MS)
    elseif NEI == 3
        NI += TaskMove(m, p, S, sol, MS)
    elseif NEI == 4
        NI += Swap(m, n, p, S, sol, MS)
    elseif NEI == 5
        NI += TwoShift(m, p, S, sol, MS)
    elseif NEI == 6
        NI += DirectSwap(m, n, p, S, sol, MS)
    end

    return(NI)
end

function UpdateSolution(sol::Vector{Vector{Int16}}, new_sol::Vector{Vector{Int16}},
    MS::Vector{Int32}, new_MS::Vector{Int32}, m::Int8)
    #----- Update a solution

    for i in 1:m 
        size::Int16 = length(sol[i])
        
        while size != 0 
            popfirst!(sol[i])
            size -= 1
        end

        for j in eachindex(new_sol[i])
            push!(sol[i], new_sol[i][j])
        end

        MS[i] = new_MS[i]
    end
end

function Main_SA(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int; r=nothing, M=nothing)
    _set_niche!(Int(m), Int(n), r, M)   # NIS: pure (r=M=nothing) -> guard'lar no-op, equivalence korunur
    #----- Parameter declaration

    # [AYAR 2026-10-10, on-kayit protokolu madde 4] parametreler disaridan verilebilir;
    # default = published value (behaviour is bit-identical when the env variable is unset).
    SAmax::Int32 = parse(Int32, get(ENV, "SA_SAMAX", "1176628"))
    alpha::Float16 = parse(Float16, get(ENV, "SA_ALPHA", "0.96"))
    T0::Float16 = parse(Float16, get(ENV, "SA_T0", "1"))
    Iter::Int32 = 1
    I::Int32 = 0 # Counter for the number of iterations
    NI::Int64 = 0 # Counter for the number of objective function evaluations

    #----- Initial solution 

    Inc_sol = InitialSolution(m, n)
    Inc_MS = zeros(Int32, m) 

    for i::Int8 in 1:m
        Inc_MS[i] = MachineSpan(i, p, S, Inc_sol)
        NI += 1
    end
    
    Inc_Cmax::Int32 = maximum(Inc_MS)

    #----- Initializes a new solution

    New_sol = deepcopy(Inc_sol)
    New_MS = deepcopy(Inc_MS)
    New_Cmax::Int32 = Inc_Cmax

    #----- Initializes the best solution 

    best_sol = deepcopy(Inc_sol)
    best_MS = deepcopy(Inc_MS)
    best_Cmax = maximum(Inc_MS)

    #----- Declaration of time variables

    elapsed::Float64 = 0
    time_limit::Float64 = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    start_time::Float64 = time()
    tbest::Float64 = 0.0   # en iyiyi bulma ani (sn)
    
    #----- Start of SA algorithm 
    
    while elapsed <= time_limit

        NI += LocalSearch(New_sol, New_MS, m, n, p, S)

        New_Cmax = maximum(New_MS)
        delta::Int32 = New_Cmax - Inc_Cmax

        if delta <= 0 
            UpdateSolution(Inc_sol, New_sol, Inc_MS, New_MS, m)
            Inc_Cmax = New_Cmax

            if New_Cmax < best_Cmax
                best_Cmax = New_Cmax
                UpdateSolution(best_sol, New_sol, best_MS, New_MS, m)
                tbest = time() - start_time
            end
        else
            r = rand()
            if r < exp(-delta/T0)
                UpdateSolution(Inc_sol, New_sol, Inc_MS, New_MS, m)
                Inc_Cmax = New_Cmax
            else
                UpdateSolution(New_sol, Inc_sol, New_MS, Inc_MS, m)
                New_Cmax = Inc_Cmax
            end
        end
            
        if Iter >= SAmax
            T0 *= alpha
            Iter = 1
        end

        Iter += 1
        I += 1
        elapsed = time() - start_time
    end
    
    # [DIS-DENETIM] best_sol da donduruluyor: run_one.jl bunu SOL satirina basar, Python
    # tarafi feasibility.py ile denetler. Zaman dongusunun DISINDA, salt-okunur, RNG cekmez
    # -> arama davranisi ve sure BIREBIR ayni kalir.
    return(best_Cmax, I, NI, tbest, best_sol)
end